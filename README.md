<div align="center">

# On-ieum

### Integrated Public Transportation AIoT System for the Digitally Vulnerable

#### Capstone Project, Kangwon National University

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
4. [Physical Custom Hardware](#physical-custom-hardware)
5. [Demo Video](#demo-video)
6. [References](#references)
7. [Contact Information](#contact-information)

</div>

---

## Overview



---

## Motivation

In modern world, utilizing smart-phone abilities are important and basic skills for living many areas. Especially, using public transit networks such as Buses, Subways, and Trains. However, the main center of cities are highly dense and complex. For example, Seoul that Capital of South Korea is the one of the dense areas. The Seoul subways and buses system provide many public transit networks and it's highly complex. Even younger people that familiar with smartphone, it is quite difficult using Seoul's transit networks. The digitally vulnerable people will be more complex than younger people. To address this, we develop Guided Transportation AIoT System that does not require Smartphone, it's called "On-Ieum".

---

## On-Ieum Pipeline

<div align="center">

![On-ieum Pipeline](./assets/onieum_pipeline.png)

</div>

### System Architecture

| Component | Device | Role |
|-----------|--------|------|
| Face Detection | Raspberry Pi 5 + Hailo-8 | SCRFD + ArcFace |
| Speech-to-Text | Raspberry Pi 5 | Faster-Whisper (whisper-small-ko) |
| LLM Inference | Jetson Orin Nano | EXAONE-3.5-2.4B (llama.cpp) |
| Route Search | Jetson Orin Nano | Kakao API + ODsay API |
| UI | Raspberry Pi 5 | Flask + HTML/CSS |
| Receipt | Raspberry Pi 5 | ESC/POS Thermal Printer |

---

## Physical Custom Hardware



---

## Demo Video

<div align="center">



</div>

---

## References



---

## Contact Information

If you need to reach this project or have questions,

Technical Leader : Dongjun Kim (dongjun.kim.eecs@gmail.com)

---

<div align="center">

**Kangwon National University · Capstone Project · 2025**

</div>
