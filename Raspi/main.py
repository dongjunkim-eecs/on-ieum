import os
import sys
import cv2
import json
import time
import uuid
import threading
import numpy as np
import sounddevice as sd
import soundfile as sf
import grpc
import capstone_pb2
import capstone_pb2_grpc
from pathlib import Path
from flask import Flask, render_template, Response, jsonify, request
from picamera2 import Picamera2
from faster_whisper import WhisperModel
from hailo_platform import VDevice, HEF, ConfigureParams, HailoStreamInterface, \
    InputVStreamParams, OutputVStreamParams, InferVStreams, FormatType

# ---------------------------------------------------------------
# Environment Settup
# ---------------------------------------------------------------
os.environ['QT_QPA_PLATFORM'] = 'offscreen'

JETSON_IP = "192.168.1.11:50051"
SAMPLE_RATE = 44100
RECORD_SECONDS = 5
DB_PATH = Path("face_db.json")
WHISPER_MODEL_PATH = "/home/user/whisper-small-ko-ct2"

whisper_model = None
infer_pipeline = None
activated_ng = None

app = Flask(__name__)

# ---------------------------------------------------------------
# State
# ---------------------------------------------------------------
state = {
    "phase": "idle",       # idle / face / listening / processing / result
    "user_id": None,
    "is_new_user": False,
    "stt_text": "",
    "ai_reply": "",
    "error": "",
    "process_step":""
}
state_lock = threading.Lock()

frame_ref = [None]
frame_lock = threading.Lock()
face_results_ref = [[]]
face_results_lock = threading.Lock()

# ---------------------------------------------------------------
# Face Recognition Model
# ---------------------------------------------------------------
face_cascade = cv2.CascadeClassifier(
    '/usr/share/opencv4/haarcascades/haarcascade_frontalface_default.xml'
)

# ---------------------------------------------------------------
# DB 
# ---------------------------------------------------------------
def load_db():
    if DB_PATH.exists():
        try:
            with open(DB_PATH) as f:
                data = json.load(f)
            return {k: [np.array(e) for e in v] for k, v in data.items()}
        except:
            pass
    return {}

def save_db(db):
    with open(DB_PATH, 'w') as f:
        json.dump({k: [e.tolist() for e in v] for k, v in db.items()}, f)

def cosine_sim(a, b):
    a = a / (np.linalg.norm(a) + 1e-6)
    b = b / (np.linalg.norm(b) + 1e-6)
    return float(np.dot(a, b))

def identify_or_register(embedding, db, threshold=0.55):
    best_id, best_score = None, -1
    for uid, embs in db.items():
        score = max(cosine_sim(embedding, e) for e in embs)
        if score > best_score:
            best_score, best_id = score, uid
    if best_id and best_score >= threshold:
        if len(db[best_id]) < 20:
            db[best_id].append(embedding)
            save_db(db)
        return best_id, best_score, False
    else:
        new_id = "user_" + uuid.uuid4().hex[:6]
        db[new_id] = [embedding]
        save_db(db)
        return new_id, 1.0, True

# ---------------------------------------------------------------
# Camera + Face Model Theread
# ---------------------------------------------------------------
def camera_thread(picam2, arcface_ng, arc_in, arc_out, a_in_name, a_out_name, stop_event):
    db = load_db()
    
    vote_list = []        #  [(uid, is_new), ...]
    vote_start_time = None
    VOTE_DURATION = 5.0
    MIN_VOTES = 3
    
    while not stop_event.is_set():
        try:
            raw = picam2.capture_array("main")
            frame = cv2.cvtColor(raw, cv2.COLOR_RGB2BGR)

            with frame_lock:
                frame_ref[0] = frame.copy()

            with state_lock:
                current_phase = state["phase"]

            if current_phase == "face":
                gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
                faces = face_cascade.detectMultiScale(gray, 1.1, 5, minSize=(80, 80))

                new_results = []
                for (x, y, w, h) in faces:
                    if w < 100 or h < 100:
                        continue

                    face_rgb = cv2.cvtColor(
                        cv2.resize(frame[y:y+h, x:x+w], (112, 112)),
                        cv2.COLOR_BGR2RGB
                    )
                    # with InferVStreams(arcface_ng, arc_in, arc_out) as pipe:
                    #     with arcface_ng.activate(arcface_ng.create_params()):
                    #         ar = pipe.infer({a_in_name: np.expand_dims(face_rgb, 0)})
                    ar = infer_pipeline.infer({a_in_name: np.expand_dims(face_rgb, 0)})
                    embedding = ar[a_out_name][0]
                    uid, sim, is_new = identify_or_register(embedding, db)
                    new_results.append((x, y, x+w, y+h, uid, sim, is_new))

                    if vote_start_time is None:
                        vote_start_time = time.time()
                        print("[Start Vote]")

                    vote_list.append(uid)
                    print(f"[Vote] {uid} (Total {len(vote_list)} vote)")

                with face_results_lock:
                    face_results_ref[0] = new_results

                if vote_start_time and (time.time() - vote_start_time) >= VOTE_DURATION:
                    print(f"[Vote Completed] Total: {vote_list}")

                    if len(vote_list) >= MIN_VOTES:
                        from collections import Counter
                        best_uid = Counter(vote_list).most_common(1)[0][0]
                        best_count = Counter(vote_list).most_common(1)[0][1]
                        is_new = best_uid not in db or len(db.get(best_uid, [])) <= 1
                        print(f"[Confirmed] {best_uid} ({best_count}/{len(vote_list)})")

                        with state_lock:
                            if state["phase"] == "face":
                                state["user_id"] = best_uid
                                state["is_new_user"] = is_new
                                state["phase"] = "listening"
                    else:
                        print(f"[Not Enough Voting] {len(vote_list)} - Retry")

                    # 투표 리셋
                    vote_list = []
                    vote_start_time = None

        except Exception as e:
            print(f"Camera Theread Error: {e}")
        time.sleep(0.3)
# ---------------------------------------------------------------
# Streaming
# ---------------------------------------------------------------
def generate_frames():
    while True:
        with frame_lock:
            frame = frame_ref[0]

        if frame is None:
            time.sleep(0.05)
            continue

        display = frame.copy()
        ret, buffer = cv2.imencode('.jpg', display, [cv2.IMWRITE_JPEG_QUALITY, 80])

        with face_results_lock:
            results = face_results_ref[0][:]

        for (x1, y1, x2, y2, uid, sim, is_new) in results:
            color = (76, 175, 130) if not is_new else (255, 152, 76)
            cv2.rectangle(display, (x1, y1), (x2, y2), color, 3)
            label = f"{uid}"
            (tw, th), _ = cv2.getTextSize(label, cv2.FONT_HERSHEY_SIMPLEX, 0.8, 2)
            cv2.rectangle(display, (x1, y1-th-14), (x1+tw+8, y1), color, -1)
            cv2.putText(display, label, (x1+4, y1-6),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.8, (255, 255, 255), 2)

        ret, buffer = cv2.imencode('.jpg', display, [cv2.IMWRITE_JPEG_QUALITY, 80])
        if ret:
            yield (b'--frame\r\n'
                   b'Content-Type: image/jpeg\r\n\r\n' + buffer.tobytes() + b'\r\n')
        time.sleep(0.033)

# ---------------------------------------------------------------
# STT + gRPC
# ---------------------------------------------------------------
def record_and_process():
    global whisper_model
    try:
        audio = sd.rec(
        int(RECORD_SECONDS * SAMPLE_RATE),
        samplerate=SAMPLE_RATE,
        channels=1,
        dtype='int16',
        device=1
        )
        sd.wait()
        sf.write('/tmp/onieum_recording.wav', audio, SAMPLE_RATE)

        with state_lock:
            state["phase"] = "processing"
            state["process_step"] = "stt"

        # STT
        segments, _ = whisper_model.transcribe(
    '/tmp/onieum_recording.wav', language="ko", beam_size=1, vad_filter=True, vad_parameters=dict(min_silence_duration_ms=500)
)
        full_text = " ".join([s.text for s in segments]).strip()

        with state_lock:
            state["stt_text"] = full_text
            state["process_step"] = "sending"

        if not full_text:
            with state_lock:
                state["error"] = "Can't reconginize audio"
                state["phase"] = "error"
            return

        # gRPC send
        with state_lock:
            state["process_step"] = "route"

        def update_steps():
            time.sleep(8)
            with state_lock:
                if state["phase"] == "processing":
                    state["process_step"] = "llm"
            time.sleep(10)
            with state_lock:
                if state["phase"] == "processing":
                    state["process_step"] = "done_wait"

        threading.Thread(target=update_steps, daemon=True).start()

        with grpc.insecure_channel(JETSON_IP) as channel:
            stub = capstone_pb2_grpc.AIBridgeStub(channel)
            response = stub.Inference(capstone_pb2.UserRequest(text=full_text))
            ai_reply = response.reply

        with state_lock:
            state["process_step"] = "done"
            state["ai_reply"] = ai_reply
            state["phase"] = "result"
        
    except Exception as e:
        with state_lock:
            state["error"] = f"Error: {str(e)}"
            state["phase"] = "error"
# ---------------------------------------------------------------
# Flask Route
# ---------------------------------------------------------------
@app.route('/')
def index():
    return render_template('index.html')

@app.route('/video_feed')
def video_feed():
    return Response(generate_frames(),
                    mimetype='multipart/x-mixed-replace; boundary=frame')

@app.route('/state')
def get_state():
    with state_lock:
        return jsonify(state.copy())

@app.route('/start', methods=['POST'])
def start():
    with state_lock:
        state["phase"] = "face"
        state["user_id"] = None
        state["is_new_user"] = False
        state["stt_text"] = ""
        state["ai_reply"] = ""
        state["error"] = ""
    with face_results_lock:
        face_results_ref[0] = []
    return jsonify({"ok": True})

@app.route('/start_listen', methods=['POST'])
def start_listen():
    with state_lock:
        state["phase"] = "listening"
    threading.Thread(target=record_and_process, daemon=True).start()
    return jsonify({"ok": True})

@app.route('/reset', methods=['POST'])
def reset():
    with state_lock:
        state["phase"] = "idle"
        state["user_id"] = None
        state["stt_text"] = ""
        state["ai_reply"] = ""
        state["error"] = ""
    with face_results_lock:
        face_results_ref[0] = []
    return jsonify({"ok": True})

# ---------------------------------------------------------------
# Main
# ---------------------------------------------------------------
if __name__ == '__main__':
    print("Load Model...")
    whisper_model = WhisperModel(WHISPER_MODEL_PATH, compute_type="int8")
    print("Whisper Model Load Complete")
    arcface_hef = HEF("/usr/local/hailo/resources/models/hailo8/arcface_mobilefacenet.hef")

    vd = VDevice()
    arcface_ng = vd.configure(
        arcface_hef,
        ConfigureParams.create_from_hef(arcface_hef, HailoStreamInterface.PCIe)
    )[0]
    arc_in = InputVStreamParams.make(arcface_ng, format_type=FormatType.UINT8)
    arc_out = OutputVStreamParams.make(arcface_ng, format_type=FormatType.FLOAT32)
    a_in_name = arcface_hef.get_input_vstream_infos()[0].name
    a_out_name = arcface_hef.get_output_vstream_infos()[0].name

    infer_pipeline = InferVStreams(arcface_ng, arc_in, arc_out)
    infer_pipeline.__enter__()
    activated_ng = arcface_ng.activate(arcface_ng.create_params())
    activated_ng.__enter__()
    print("ArcFace Pipeline Completed")

    picam2 = Picamera2()
    config = picam2.create_preview_configuration(
        main={"size": (1280, 720), "format": "BGR888"}
    )
    picam2.configure(config)
    picam2.start()
    time.sleep(1)
    print("Start Camera")

    stop_event = threading.Event()
    cam_thread = threading.Thread(
        target=camera_thread,
        args=(picam2, arcface_ng, arc_in, arc_out, a_in_name, a_out_name, stop_event),
        daemon=True
    )
    cam_thread.start()

    print("Start Server: http://localhost:5000")
    try:
        app.run(host='0.0.0.0', port=5000, debug=False, threaded=True)
    finally:
        stop_event.set()
        if activated_ng:
            activated_ng.__exit__(None, None, None)
        if infer_pipeline:
            infer_pipeline.__exit__(None, None, None)
        picam2.stop()
        vd.release()
