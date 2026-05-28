<div align="center">

# 🌱 AIgriculture

**An open-source smart farm system for Raspberry Pi.**
Monitor soil moisture, automate irrigation, detect disease, and chat with your farm using AI — all from a single web dashboard.

[![English](https://img.shields.io/badge/lang-English-blue?style=for-the-badge)](README.md)
[![日本語](https://img.shields.io/badge/lang-日本語-red?style=for-the-badge)](README.ja.md)
[![हिन्दी](https://img.shields.io/badge/lang-हिन्दी-orange?style=for-the-badge)](README.hi.md)
[![Русский](https://img.shields.io/badge/lang-Русский-green?style=for-the-badge)](README.ru.md)

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)
[![Python 3.11+](https://img.shields.io/badge/python-3.11+-blue.svg)](https://www.python.org/downloads/)
[![Raspberry Pi](https://img.shields.io/badge/Raspberry%20Pi-4%20%7C%205-c51a4a)](https://www.raspberrypi.com/)
[![Docker](https://img.shields.io/badge/Docker-ready-2496ed)](https://docs.docker.com/)

</div>

---

![Farm overview](docs/assets/big_farm.jpeg)

---

## What it does

| Subsystem | What you get |
|-----------|-------------|
| **Irrigation** | 8-plant burst irrigation with auto-mode (trigger at 45 % moisture, stop at 65 %, hardlock at 70 %) |
| **FarmMonitor** | Periodic YOLO scan for disease (5 classes) and ripeness (5 stages); email alert on detection |
| **Security camera** | Real-time person / animal detection with dual-buzzer siren; MJPEG stream in dashboard |
| **FLORA AI** | Multi-provider chat assistant (Groq / Cerebras / Mistral / Gemini) with farm tool use; offline fallback |
| **Meshtastic** | LoRa bridge — FLORA answers any channel or DM from your mesh network |
| **Dashboard** | Dark-theme single-page app: overview, cameras, AI chat, events log, settings |

---

## 🛠️ Hardware — Beginner / Testing build

Don't have a real farm yet? **You don't need one.** Here's the smallest kit that turns AIgriculture into a working desk-top prototype. Every line below is a beginner-friendly substitution for the full build.

| # | Component | Why you need it | Beginner tip |
|---|-----------|-----------------|--------------|
| 1 | **Raspberry Pi 4 / 5** (4 GB+, 8 GB recommended)<br><img src="docs/assets/hardware/Raspberrypi_5.png" width="240"> | Runs the whole stack — dashboard, AI, irrigation logic. | Pi 5 is fastest, but a Pi 4 (2 GB) is enough to try it. Flash **Raspberry Pi OS Bookworm 64-bit**. |
| 2 | **ADS1115 16-bit I²C ADC**<br><img src="docs/assets/hardware/adc_module.png" width="240"> | The Pi has no analog input. Capacitive moisture sensors are analog, so the ADC translates them into numbers the Pi can read. | One ADS1115 = 4 sensors. Buy **two** (`0x48` + `0x49`) for the default 8-plant build, or up to **four** (`0x48`-`0x4B`) for 16 plants. |
| 3 | **Capacitive soil-moisture sensor**<br><img src="docs/assets/hardware/moisture_sensor.png" width="240"> | Reads how wet the soil is — the input that drives auto-irrigation. | Use **capacitive** (yellow PCB), not the cheap resistive ones — they corrode within weeks. One per plant. |
| 4 | **8-channel relay board** (active-LOW, opto-isolated)<br><img src="docs/assets/hardware/relay_module.png" width="240"> | Lets the Pi switch the pumps on and off. The Pi itself cannot supply pump power. | Make sure it's labelled **5 V trigger, opto-isolated**, otherwise it won't fire from the Pi's 3.3 V pins. |
| 5 | **Small 5 V or 12 V DC water pump**<br><img src="docs/assets/hardware/water_pump.png" width="240"> | The thing that actually waters the plant. | One per plant. **Power them from a separate supply, never from the Pi's 5 V rail.** The Pi only controls the relay, not the current. |
| 6 | **Raspberry Pi Camera (CSI)** *or* **USB webcam**<br><img src="docs/assets/hardware/pi-camera.jpeg" width="200"> &nbsp; <img src="docs/assets/hardware/usb_camera.png" width="200"> | One feeds the FarmMonitor disease/ripeness scan; one feeds the security camera. | A single camera is fine to start — just pass `--security-camera` and skip `--farm-camera`. RTSP IP cameras work too. |
| 7 | **Breadboard + jumper wires**<br><img src="docs/assets/hardware/breadboard_and_jumper_wires.png" width="240"> | To wire everything up without soldering. | Get female-to-female jumpers for sensor-to-ADC and male-to-female for ADC-to-Pi. |
| **+** | **Hailo-10H AI HAT** *(optional, faster vision)*<br><img src="docs/assets/hardware/hailo10h_optional.png" width="240"> | Hardware-accelerated YOLO inference. Cuts disease/ripeness scan time dramatically. | **Skip this for the beginner build.** The CPU path runs on a plain Pi just fine. Add Hailo only if you want faster scans or higher-res security cam. |
| **+** | **Meshtastic LoRa radio** *(optional, off-grid chat)*<br><img src="docs/assets/hardware/LORA_chip_with_433hz_antenna.png" width="240"> | Chat with FLORA from outside Wi-Fi range over a LoRa mesh. | Optional. Heltec / LilyGo boards with 433 / 868 / 915 MHz antennas all work. Skip if you only need the web UI. |

**Minimum testing build** (just to play with the dashboard on a desk):
> 1 × Pi · 1 × ADS1115 · 1 × moisture sensor · 1 × USB camera. That's it. No relays, no pumps, no Hailo. Use the "+ Add sensors" button in the dashboard once it's up.

---

## 🚀 Quick start

```bash
git clone https://github.com/darkphantom-gamer/AIgriculture.git
cd AIgriculture
cp .env.example .env            # then EDIT .env (see next section)
docker compose up -d
```

Open `http://<pi-ip>:8000`.

> **Running on a laptop / non-Pi?** This still works. GPIO and I2C silently no-op when the hardware isn't there — you get the full dashboard, AI chat, and (USB / network) cameras.

See [docs/SETUP.md](docs/SETUP.md) for native install, systemd service, and Hailo setup.

---

## 🔑 You MUST add your own credentials

**Nothing in this repo contains real API keys, passwords, or emails — that's by design.**
After `cp .env.example .env`, open `.env` and fill in your own:

| In `.env` | What to put | Where to get it |
|-----------|-------------|-----------------|
| `ADMIN_USER` | The dashboard username you want | (you choose) |
| `ADMIN_PASS` | A strong password | (you choose) — if left blank, a random one prints on first boot |
| `GROQ_API_KEY` | Your Groq key (recommended, fast & free) | https://console.groq.com |
| `CEREBRAS_API_KEY` | Your Cerebras key (optional) | https://cloud.cerebras.ai |
| `MISTRAL_API_KEY` | Your Mistral key (optional) | https://console.mistral.ai |
| `GEMINI_API_KEY` | Your Google AI Studio key (optional) | https://aistudio.google.com |

Set **any one** AI provider and FLORA gets full tool-using chat. Leave them all empty and FLORA still works offline with keyword routing.

For **email alerts** (FarmMonitor disease notifications, FLORA reports):
```bash
cp config.example.yaml config.yaml      # then edit config.yaml
```

Inside `config.yaml`, put your own SMTP credentials — Gmail (with an *app password*), Hostinger, your school mail, anything that speaks SMTP:

```yaml
smtp:
  host: smtp.gmail.com          # or smtp.hostinger.com, smtp.office365.com, etc.
  port: 587
  email: you@your-domain.com    # your real address
  password: your-app-password   # NOT your normal mail password — use an app password
  from_email: you@your-domain.com
notifications:
  to_email: alerts@your-domain.com
```

> **Gmail tip:** turn on 2-Step Verification, then create an **App Password** at https://myaccount.google.com/apppasswords and paste that. Normal Gmail passwords are rejected by SMTP.

`.env` and `config.yaml` are both git-ignored — your real secrets never end up in the repo.

---

## 🔌 Wiring (change one file to match your board)

Default pin map matches the reference build in [`aigriculture.txt`](aigriculture.txt):

| Component | Default BCM pins |
|-----------|------------------|
| 8 pump relays (Plant A → H) | `17, 27, 22, 23, 5, 6, 13, 19` (active LOW) |
| 2 buzzer siren | `18, 12` (2700 Hz) |
| 8 moisture sensors | ADS1115 × 2 at I²C `0x48` and `0x49` |
| I²C bus | `/dev/i2c-1` |
| GPIO chip | `/dev/gpiochip0` (auto-tries `4` for Pi 5 if 0 fails) |

**To use different pins**, you do NOT need to edit any Python:

```bash
cp wiring.example.yaml wiring.yaml      # then edit wiring.yaml
# For Docker, also uncomment the wiring.yaml volume in docker-compose.yml.
docker compose up -d --force-recreate
```

`wiring.yaml` lets you remap any pin, flip active-high/active-low, change buzzer count or frequency, and recalibrate moisture sensors — all without touching code.

---

## Dashboard

![Dashboard status](docs/assets/dashboard_status.png)

Five tabs: **Overview** (live moisture + pump control), **Cameras** (MJPEG streams), **FLORA** (AI chat), **Events** (alert log), **Settings** (notifications + siren).

---

## FLORA AI assistant

![FLORA preview](docs/assets/FLORA_preview.jpeg)

FLORA understands natural language commands:

- *"Water plant A"* → triggers burst irrigation
- *"What is the moisture level of all plants?"* → reads all sensors
- *"Stop the pump on C"* → stops pump C
- *"Is there any disease detected?"* → checks latest FarmMonitor scan

FLORA works completely offline when no API keys are set, using keyword routing.

### Architecture

| Layer | Role |
|-------|------|
| ![Layer 1](docs/assets/FLORA_first_layer_Architecture.png) | Provider routing + fallback |
| ![Layer 2](docs/assets/FLORA_Second_layer_Architecture.png) | Tool dispatch (sensors, pumps, camera, scheduler) |
| ![Layer 3](docs/assets/FLORA_Third_Lasyer_Architecture.png) | Offline keyword rules |

---

## FarmMonitor

![Farm Monitor architecture](docs/assets/Farm_Monitor_Core_Architecture.png)

Runs scheduled full-field scans. Captures a batch of frames, filters blurry ones, then runs disease and ripeness detection.

![Farm Monitor result](docs/assets/Farm_Monitor_Result.png)

Results are saved to `runtime/farmmonitor/` as JSON + JPEG. If disease is detected and SMTP is configured, an email alert is sent.

---

## Security camera

![Security camera result](docs/assets/Security_camera_result.png)

Frame-skip inference (every Nth frame) with a class allow-list keeps CPU usage low. On threat detection, the siren arms for 8 seconds and a snapshot is saved.

---

## Meshtastic LoRa bridge

![Meshtastic](docs/assets/MEshtastic.png)

Set `MESH_ENABLED=true` and point `MESH_HOST` at your node. FLORA listens on any channel or DM and replies only to the sender — works completely off-grid.

---

## Storage

![Storage](docs/assets/Storage_Data_screenshot.png)

All captured frames, farm scans, and security snapshots are browsable from the dashboard Events tab and the storage API.

---

## Camera options

```bash
# Raspberry Pi CSI camera
python -m aigriculture --security-camera csi:0 --farm-camera csi:1

# USB camera
python -m aigriculture --security-camera /dev/video0 --farm-camera /dev/video1

# Network / RTSP camera
python -m aigriculture --security-camera rtsp://user:pass@192.168.1.10/live
```

In Docker, uncomment the relevant `command:` line in `docker-compose.yml`.

---

## 🧠 Plug in your own ML models

The disease and ripeness detectors are just **Ultralytics YOLO `.pt` files**.
Train them on your own crop, drop them into `models/`, point the app at them — done.

```bash
# Native run
python -m aigriculture \
  --disease-model  models/my_strawberry_disease.pt \
  --ripeness-model models/my_tomato_ripeness.pt

# Docker — mount your models directory over the bundled one
# (uncomment the `./models:/app/models:ro` line in docker-compose.yml)
docker compose up -d
```

What "compatible" means in practice:
- Any model exported by `yolo export ... format=onnx` or trained with `ultralytics` works.
- For the **security camera**, swap with `--model my_yolo.pt` (default `yolo11n.pt` auto-downloads on first run).
- For **Hailo**, you'll need a `.hef` compiled with the Hailo Dataflow Compiler — see [`models/README.md`](models/README.md).

The bundled strawberry models are a starting point, not a hard requirement.

---

## Hailo (optional)

```bash
# Install HailoRT SDK on the host first (see models/README.md), then:
pip install -r requirements-hailo.txt
python -m aigriculture --backend hailo

# Or with Docker
docker compose -f docker-compose.yml -f docker-compose.hailo.yml up -d
```

---

## CLI reference

```
python -m aigriculture [options]

  --host              bind address (default: 0.0.0.0)
  --port              port (default: 8000)
  --security-camera   camera spec for security feed (csi:N | /dev/videoN | rtsp://...)
  --farm-camera       camera spec for FarmMonitor feed
  --backend           cpu (default) | hailo
  --model             YOLO model for security camera (default: yolo11n.pt)
  --imgsz             inference input size (default: 480)
  --detect-every      skip N frames between detections (default: 3)
  --disease-model     path to disease .pt (default: models/Disease_detect.pt)
  --ripeness-model    path to ripeness .pt (default: models/Ripeness_detect.pt)
```

---

## Project layout

```
AIgriculture/
├── aigriculture/         # Python package
│   ├── camera/           # CSI / USB / RTSP backends
│   ├── farmmonitor/      # disease + ripeness scanning
│   ├── flora/            # AI assistant + tools
│   ├── hardware/         # gpio + moisture, both read wiring.yaml
│   ├── inference/        # YOLO CPU + Hailo backends
│   ├── mesh/             # Meshtastic LoRa bridge
│   ├── security/         # intruder detection
│   └── web/              # FastAPI app + dashboard HTML
├── docs/
│   ├── SETUP.md          # detailed setup guide
│   └── assets/           # images used in this README
├── labels/               # YOLO class labels (JSON)
├── models/               # bundled .pt + .hef weights
├── .env.example          # ← copy to .env and edit
├── config.example.yaml   # ← copy to config.yaml and edit (for email)
├── wiring.example.yaml   # ← copy to wiring.yaml and edit (for custom pins)
├── docker-compose.yml
├── Dockerfile
└── aigriculture.txt      # complete hand-off spec
```

---

## License

MIT — see [LICENSE](LICENSE).
