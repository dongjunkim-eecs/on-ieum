<div align="center">

# On-ieum

### Integrated Public Transportation AIoT System for the Digitally Vulnerable

#### Capstone Project, Kangwon National University; Department of Electronic and Semiconductor Engineering

Team Member : Seung-Gyu Choi, Dongjun Kim, Jae-seo Choi, Soobin Choi, Minseo Kim <br>
Technical Lead : Dongjun Kim

<br>

![Python](https://img.shields.io/badge/Python-3.13-blue?logo=python)
![Raspberry Pi](https://img.shields.io/badge/Raspberry%20Pi-5-red?logo=raspberrypi)
![NVIDIA](https://img.shields.io/badge/NVIDIA-Jetson%20Orin%20Nano-green?logo=nvidia)
![Hailo](https://img.shields.io/badge/Hailo-AI%20HAT+-orange)
![License](https://img.shields.io/badge/License-MIT-yellow)

</div>

---

<div align="left">

## Table of Contents

1. [Overview](#overview)
2. [Motivation](#motivation)
3. [On-Ieum Pipeline](#on-ieum-pipeline)
4. [Getting Started](#getting-started)
5. [Physical Custom Hardware](#physical-custom-hardware)
6. [Demo Video](#demo-video)
7. [Contact Information](#contact-information)

</div>

---

## Overview

We developed an integrated AIoT system, "On-Ieum," to provide public transportation guidance without requiring a smartphone.

On-Ieum consists of multiple AI models, including Face Recognition, Speech-to-Text, and an On-Device LLM, all running exclusively on edge devices (Raspberry Pi 5 and Jetson Orin Nano).

---

## Motivation

In the modern world, the ability to use a smartphone has become an essential skill for daily life in many areas, especially for navigating public transit networks such as buses, subways, and trains. However, major city centers are highly dense and complex. For example, Seoul, the capital of South Korea, is one of the densest metropolitan areas, and its extensive subway and bus networks are extremely intricate. Even younger people who are familiar with smartphones often find it difficult to navigate Seoul's transit systems. For the digitally vulnerable, this challenge is even greater. To address this, we developed a guided transportation AIoT system that does not require a smartphone, named "On-Ieum."

### Meaning of On-Ieum

The name "On-Ieum" can be understood in two ways. In Korean, "On" represents warmth, while "Ieum" signifies connection.

Together, On-Ieum reflects our goal of building an AIoT transportation system that fosters a warm connection with digitally vulnerable populations.

---

## On-Ieum Pipeline

<div align="center">

![On-ieum Pipeline](./assets/onieum_pipeline.png)

</div>

### System Architecture

- Hardware : [Raspberry Pi 5 (8GB)](https://www.raspberrypi.com/products/raspberry-pi-5/) with [AI HAT+(Hailo-8 NPU)](https://www.raspberrypi.com/documentation/accessories/ai-hat-plus.html) [Jetson Orin Nano (8GB)](https://www.nvidia.com/en-us/autonomous-machines/embedded-systems/jetson-orin/nano-super-developer-kit/)
- Face Recognition Model : [SCRFD-10G (at Hailo-8 NPU)](https://github.com/deepinsight/insightface/blob/master/detection/scrfd/README.md)
- Face Embedding Model : [ArcFace MobileFaceNet (at Hailo-8 NPU)](https://arxiv.org/pdf/1804.07573)
- Speech-to-Text Model : [Faster-Whisper whisper-small-ko (at Raspberry Pi 5 CPU)](https://huggingface.co/SungBeom/whisper-small-ko)
- On-Device LLM : [LG EXAONE 3.5 2.4B-Q4 (at Jetson Orin Nano)](https://huggingface.co/LGAI-EXAONE/EXAONE-3.5-2.4B-Instruct)
- Public Transport API : [Kakao Map API for extracting the destination coordinates](https://apis.map.kakao.com/) and [ODsay Lab for guiding to the destination](https://lab.odsay.com/)
-  Peripherals : [Raspberry Pi Camera](https://www.raspberrypi.com/products/camera-module-3/) and Microphone(Britz BE-STM300)
  
---

## Getting Started 

To start On-Ieum, you need to prepare **Raspberry Pi 5** and **Jetson Orin Nano**.

Additionally, the Jetson Orin Nano and Raspberry Pi 5 are connected via an Ethernet cable for gRPC communication. 

### Installation

**1. Clone the repository**
```bash
git clone https://github.com/dongjunkim-eecs/on-ieum.git
cd on-ieum
```

**2. Generate gRPC files (both devices)**
```bash
pip install grpcio grpcio-tools
python -m grpc_tools.protoc -I. --python_out=. --grpc_python_out=. capstone.proto
```

**3. Raspberry Pi 5 setup**
```bash
pip install -r requirements_raspi.txt
```

Download STT model:
```bash
pip install ctranslate2 transformers
ct2-transformers-converter \
  --model SungBeom/whisper-small-ko \
  --output_dir ~/whisper-small-ko-ct2 \
  --quantization int8
```

**4. Jetson Orin Nano setup**
```bash
pip install -r requirements_jet.txt
```

Download LLM:
```bash
huggingface-cli download \
  LGAI-EXAONE/EXAONE-3.5-2.4B-Instruct-GGUF \
  EXAONE-3.5-2.4B-Instruct-Q4_K_M.gguf
```

---

### API Keys

Set environment variables on the Jetson:
```bash
export KAKAO_REST_KEY="your_kakao_api_key"
export ODSAY_API_KEY="your_odsay_api_key"
```

> Kakao API: https://developers.kakao.com  
> ODsay API: https://lab.odsay.com

---

### Run

**1. Start gRPC server on Jetson Orin Nano**
```bash
cd jetson
python server_llm_map.py
```

**2. Start main system on Raspberry Pi 5**
```bash
cd raspberry_pi
python main.py
```

**3. Open browser on Raspberry Pi**
```
http://localhost:5000
```

## Physical Custom Hardware



---

## Demo Video

<a href="https://www.youtube.com/watch?v=svm2jcvozz0">
  <img src="https://img.youtube.com/vi/svm2jcvozz0/maxresdefault.jpg" width="600">
</a>

---

## Contact Information

If you need to reach this project or have questions,

Technical Leader : Dongjun Kim (dongjun.kim.eecs@gmail.com)

---

<div align="center">

**Kangwon National University · Capstone Project · 2025**

</div>
