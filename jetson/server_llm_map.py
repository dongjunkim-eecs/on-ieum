import socket
import urllib3.util.connection as urllib3_connection
import requests
import grpc
from concurrent import futures
import capstone_pb2
import capstone_pb2_grpc
from llama_cpp import Llama
import urllib.parse
import usb.core
import usb.util
import os

# ---------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------
KAKAO_REST_KEY = os.environ.get("KAKAO_REST_KEY", "")
ODSAY_API_KEY = os.environ.get("ODSAY_API_KEY", "")

def allowed_gai_family():
    return socket.AF_INET

urllib3_connection.allowed_gai_family = allowed_gai_family

MODEL_PATH = "../../EXAONE-3.5-2.4B-Instruct-Q4_K_M.gguf"

# Fixed departure point (Kangwon National University Gangneung Campus Main Gate)
START_X = "128.873885"
START_Y = "37.770209"
START_NAME = "강원대학교 강릉캠퍼스 정문"

# ---------------------------------------------------------------
# Receipt Printing (ESC/POS Thermal Printer)
# ---------------------------------------------------------------
def print_route_receipt(start_name, end_name, route_raw):
    try:
        dev = usb.core.find(idVendor=0x2aaf, idProduct=0x6014)
        if dev is None:
            print("Printer not found.")
            return

        for cfg in dev:
            for intf in cfg:
                if dev.is_kernel_driver_active(intf.bInterfaceNumber):
                    dev.detach_kernel_driver(intf.bInterfaceNumber)

        dev.set_configuration()
        cfg = dev.get_active_configuration()
        intf = cfg[(0, 0)]
        ep = usb.util.find_descriptor(
            intf,
            custom_match=lambda e:
                usb.util.endpoint_direction(e.bEndpointAddress) == usb.util.ENDPOINT_OUT
        )

        def write(data):
            ep.write(data)

        write(b'\x1c\x26')

        # Title: center align, 2x size
        write(b'\x1b\x61\x01')
        write(b'\x1d\x21\x11')
        write("온-이음 길 안내\n\n".encode('cp949'))

        # Departure / Destination: left align, 2x size
        write(b'\x1b\x61\x00')
        write(b'\x1d\x21\x11')
        write(f"출발: {start_name}\n".encode('cp949'))
        write(f"도착: {end_name}\n".encode('cp949'))
        write("- - - - - - - - - -\n".encode('cp949'))

        # Parse route string
        if "경로: " in route_raw:
            time_part = route_raw.split("경로:")[0].strip()
            route_part = route_raw.split("경로:")[1].strip()
        else:
            time_part = ""
            route_part = route_raw

        # Travel time
        write(b'\x1d\x21\x11')
        write(f"{time_part}\n\n".encode('cp949'))

        # Route steps
        steps = route_part.split(" -> ")
        for step in steps:
            write(f"- {step.strip()}\n".encode('cp949'))

        write("- - - - - - - - - -\n".encode('cp949'))
        write(b'\n\n\n\n')
        write(b'\x1d\x56\x00')  # Paper cut

        print("[Receipt printed successfully]")

    except Exception as e:
        print(f"Receipt print failed: {e}")
    finally:
        try:
            usb.util.release_interface(dev, 0)
            usb.util.dispose_resources(dev)
        except:
            pass

# ---------------------------------------------------------------
# gRPC Servicer
# ---------------------------------------------------------------
class AIBridgeServicer(capstone_pb2_grpc.AIBridgeServicer):
    def __init__(self):
        print("Loading model...")
        self.llm = Llama(
            model_path=MODEL_PATH,
            n_gpu_layers=-1,
            n_ctx=2048
        )
        print("Model loaded. Server ready.")

    def extract_place(self, text):
        """Step 1: Extract destination place name from user input using LLM"""
        prompt = (
            f"[|system|]너는 강원도 강릉 지역의 장소명을 추출하는 전문가야. "
            f"문장에서 사용자가 가고자 하는 목적지 장소명만 그대로 추출해. "
            f"절대로 임의로 다른 장소로 바꾸지 마. "
            f"오타가 명확할 때만 교정하고, 확실하지 않으면 원래 단어 그대로 출력해. "
            f"띄어쓰기로 나뉜 장소명은 붙여서 하나의 단어로 출력해. "
            f"예: '옥천 고등학교' -> '옥천고등학교'\n"
            f"장소명 단어만 출력하고 절대 부연 설명하지 마.[|이전|]"
            f"[|user|]{text}[|다음|][|assistant|]"
        )
        output = self.llm(prompt, max_tokens=10, temperature=0.0, stop=["[|", "\n", " "])
        extracted = output['choices'][0]['text'].strip()
        return extracted.replace(".", "").replace("'", "").replace('"', "")

    def get_coords(self, place_name):
        """Step 2: Get coordinates from Kakao Local API"""
        url = "https://dapi.kakao.com/v2/local/search/keyword.json"
        headers = {"Authorization": f"KakaoAK {KAKAO_REST_KEY}"}
        params = {
            "query": place_name,
            "x": START_X,
            "y": START_Y,
            "radius": 20000
        }
        try:
            res = requests.get(url, headers=headers, params=params)
            data = res.json()
            if len(data.get("documents", [])) > 0:
                doc = data["documents"][0]
                # Fallback to better match if first result doesn't match
                if place_name.replace(" ", "") not in doc['place_name'].replace(" ", ""):
                    print(f"[Warning] Requested: {place_name}, Result: {doc['place_name']} - Mismatch")
                    for d in data["documents"]:
                        if place_name.replace(" ", "") in d['place_name'].replace(" ", ""):
                            doc = d
                            break
                print(f"[Kakao] Found: {doc['place_name']} / Coords: {doc['x']}, {doc['y']}")
                return doc['x'], doc['y'], doc['place_name']
        except Exception as e:
            print(f"[Error] Kakao API failed: {e}")
        return None, None, None

    def get_public_transport(self, ex, ey):
        """Step 3: Search public transit route via ODsay API"""
        url = (
            f"https://api.odsay.com/v1/api/searchPubTransPathT"
            f"?SX={START_X}&SY={START_Y}&EX={ex}&EY={ey}&apiKey={ODSAY_API_KEY}"
        )
        try:
            res = requests.get(url)
            route_data = res.json()

            if "result" not in route_data or "path" not in route_data["result"]:
                return "대중교통 경로를 찾을 수 없습니다."

            path = route_data["result"]["path"][0]
            info = path["info"]
            summary = f"총 {info['totalTime']}분 소요. 경로: "
            steps = []

            for sub in path["subPath"]:
                traffic_type = sub["trafficType"]
                if traffic_type == 3:  # Walking
                    distance = sub["distance"]
                    if distance > 0:
                        steps.append(f"도보 {distance}m")
                elif traffic_type == 2:  # Bus
                    bus_no = sub["lane"][0]["busNo"]
                    start_station = sub["startName"]
                    end_station = sub["endName"]
                    steps.append(f"[{start_station}]에서 {bus_no}번 버스 탑승 -> [{end_station}] 하차")
                elif traffic_type == 1:  # Subway
                    subway_name = sub["lane"][0]["name"]
                    start_station = sub["startName"]
                    end_station = sub["endName"]
                    steps.append(f"[{start_station}]에서 {subway_name} 탑승 -> [{end_station}] 하차")

            return summary + " -> ".join(steps)

        except Exception as e:
            print(f"[Error] ODsay API failed: {e}")
            return "경로 정보를 가져오는 중 오류가 발생했습니다."

    def Inference(self, request, context):
        """Main gRPC inference handler"""
        user_input = request.text
        print(f"\n[Received]: {user_input}")

        # Initialize default values to prevent unbound variable errors
        route_raw = "경로 정보를 찾을 수 없습니다."
        official_name = "알 수 없는 목적지"

        try:
            # Step 1: Extract destination
            target_place = self.extract_place(user_input)
            print(f"  - Extracted destination: {target_place}")
            official_name = target_place

            # Step 2: Get coordinates via Kakao API
            ex, ey, kakao_name = self.get_coords(target_place)

            if ex and ey:
                official_name = kakao_name

                # Step 3: Get transit route via ODsay API
                route_raw = self.get_public_transport(ex, ey)
                print(f"  - Parsed route:\n    {route_raw}")

                # Step 4: Generate guidance text via LLM
                prompt = (
                    f"[|system|]"
                    f"당신은 어르신을 위한 친절한 대중교통 안내 도우미입니다.\n"
                    f"아래 경로 정보를 바탕으로 반드시 다음 형식으로만 안내하세요:\n"
                    f"1. 총 몇 분 걸리는지\n"
                    f"2. 어디서 몇 번 버스를 타는지\n"
                    f"3. 어디서 내리는지\n"
                    f"4. 내려서 몇 미터 걸어가는지\n"
                    f"규칙:\n"
                    f"- 경로 정보에 없는 내용은 절대 추가하지 마세요.\n"
                    f"- 두 문장에서 세 문장으로 간결하게 말씀드리세요.\n"
                    f"- 다정하고 천천히 말하는 말투로 안내하세요.\n"
                    f"[|이전|]"
                    f"[|user|]경로 정보: {route_raw}\n{official_name}까지 어떻게 가나요?[|다음|]"
                    f"[|assistant|]"
                )
                output = self.llm(prompt, max_tokens=200, temperature=0.1, stop=["[|"])
                final_reply = output['choices'][0]['text'].strip()
            else:
                final_reply = f"죄송해요, {target_place}의 정확한 위치를 찾지 못했어요."

        except Exception as e:
            print(f"[Server Error]: {e}")
            final_reply = "처리 중 문제가 생겼습니다. 다시 말씀해 주시겠어요?"

        print(f"[Response]: {final_reply}")

        # Print receipt
        try:
            print_route_receipt(START_NAME, official_name, route_raw)
            print("[Receipt printed successfully]")
        except Exception as e:
            print(f"[Receipt Error]: {e}")

        return capstone_pb2.AIResponse(reply=final_reply)

# ---------------------------------------------------------------
# Server
# ---------------------------------------------------------------
def serve():
    server = grpc.server(futures.ThreadPoolExecutor(max_workers=10))
    capstone_pb2_grpc.add_AIBridgeServicer_to_server(AIBridgeServicer(), server)
    server.add_insecure_port('[::]:50051')
    server.start()
    print("Jetson gRPC Server running... (Port: 50051)")
    server.wait_for_termination()

if __name__ == "__main__":
    serve()