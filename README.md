<div align="center">

# AIgriculture

**An open-source smart farm monitoring system using Raspberry Pi.**
Monitor soil moisture, automate irrigation, detect disease,detect harvest ready,notify all alerts, and chat with your farm using FLORA AI — all from a single web dashboard.

[![English](https://img.shields.io/badge/lang-English-blue?style=for-the-badge)](README.md)
[![日本語](https://img.shields.io/badge/lang-日本語-red?style=for-the-badge)](docs/ja/README.md)
[![हिन्दी](https://img.shields.io/badge/lang-हिन्दी-orange?style=for-the-badge)](docs/hi/README.md)
[![Русский](https://img.shields.io/badge/lang-Русский-green?style=for-the-badge)](docs/ru/README.md)
[![中文](https://img.shields.io/badge/lang-中文-red?style=for-the-badge)](docs/zh/README.md)

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)
[![Python](https://img.shields.io/badge/python-Pi%20native%20(3.13)-blue.svg)](https://www.python.org/downloads/)
[![Raspberry Pi](https://img.shields.io/badge/Raspberry%20Pi-4%20%7C%205-c51a4a)](https://www.raspberrypi.com/)

</div>

---

![Farm overview](docs/assets/small_prototype.jpeg)

---

## What it does

| Subsystem | What you get |
|-----------|-------------|
| **Irrigation** | Burst irrigation for as many plants as you want, with auto-mode (trigger at 45 % moisture, stop at 65 %, hardlock at 70 %) |
| **FarmMonitor** | Periodic YOLO scan for disease (5 classes) and ripeness (5 stages); email alert on detection |
| **Security camera** | Real-time person / animal detection with dual-buzzer siren; MJPEG stream in dashboard |
| **FLORA AI** | Multi-provider chat assistant (Groq / Cerebras / Mistral / Gemini) with farm tool use; offline fallback |
| **Meshtastic** | LoRa bridge — FLORA answers any channel or DM from your mesh network |
| **Dashboard** | Dark-theme single-page app: overview, cameras, AI chat, events log, settings |

The repo ships **two entry points** — pick the one that matches your hardware:

| Script | When to use | Security camera engine |
|--------|-------------|------------------------|
| **`python main.py`** | Default. Runs on any Raspberry Pi (4 / 5) or laptop. | Ultralytics YOLOv8s on CPU with frame-skip — better recall on person / bear / cow / elephant than nano, still real-time on a Pi 5. |
| **`python main-hailo.py`** | You have the Hailo-10H AI HAT installed. | Hailo HEF pipeline — ~10× faster inference. |

Everything else — dashboard, login, FLORA, FarmMonitor, irrigation, email alerts, storage, Meshtastic — is **identical** between the two. The only difference is which inference engine drives the security camera.

---

## 🛠️ Hardware — Beginner / Testing build

Don't have a real farm yet? **You don't need one.** Here's the smallest kit that turns AIgriculture into a working desk-top prototype. Every line below is a beginner-friendly substitution for the full build.

| # | Component | Why you need it | Beginner tip |
|---|-----------|-----------------|--------------|
| 1 | **Raspberry Pi 4 / 5** (4 GB+, 8 GB recommended)<br><img src="docs/assets/hardware/Raspberrypi_5.png" width="240"> | Runs the whole stack — dashboard, AI, irrigation logic. | Pi 5 is fastest, but a Pi 4 (2 GB) is enough to try it. Flash **Raspberry Pi OS Bookworm 64-bit**. |
| 2 | **ADS1115 16-bit I²C ADC**<br><img src="docs/assets/hardware/adc_module.png" width="240"> | The Pi has no analog input. Capacitive moisture sensors are analog, so the ADC translates them into numbers the Pi can read. | One ADS1115 = 4 sensors. Add as many as you need — up to **four** (`0x48`-`0x4B`) for 16 plants, or even more buses for bigger farms. |
| 3 | **Capacitive soil-moisture sensor**<br><img src="docs/assets/hardware/moisture_sensor.png" width="240"> | Reads how wet the soil is — the input that drives auto-irrigation. | Use **capacitive** (yellow PCB), not the cheap resistive ones — they corrode within weeks. One per plant. |
| 4 | **8-channel relay board** (active-LOW, opto-isolated)<br><img src="docs/assets/hardware/relay_module.png" width="240"> | Lets the Pi switch the pumps on and off. The Pi itself cannot supply pump power. | Make sure it's labelled **5 V trigger, opto-isolated**, otherwise it won't fire from the Pi's 3.3 V pins. |
| 5 | **Small 5 V or 12 V DC water pump**<br><img src="docs/assets/hardware/water_pump.png" width="240"> | The thing that actually waters the plant. | One per plant. **Power them from a separate supply, never from the Pi's 5 V rail.** The Pi only controls the relay, not the current. |
| 6 | **Raspberry Pi Camera (CSI)** *or* **USB webcam**<br><img src="docs/assets/hardware/pi-camera.jpeg" width="200"> &nbsp; <img src="docs/assets/hardware/usb_camera.png" width="200"> | One feeds the FarmMonitor disease/ripeness scan; one feeds the security camera. | A single camera is fine to start — just pass `--security-camera` and skip `--farm-camera`. RTSP IP cameras work too. |
| 7 | **Breadboard + jumper wires**<br><img src="docs/assets/hardware/breadboard_and_jumper_wires.png" width="240"> | To wire everything up without soldering. | Get female-to-female jumpers for sensor-to-ADC and male-to-female for ADC-to-Pi. |
| **+** | **Hailo-10H AI HAT** *(optional, faster vision)*<br><img src="docs/assets/hardware/hailo10h_optional.png" width="240"> | Hardware-accelerated YOLO inference. Cuts disease/ripeness scan time dramatically. | **Skip this for the beginner build.** The CPU path runs on a plain Pi just fine. Add Hailo only if you want faster scans or higher-res security cam. |
| **+** | **Meshtastic LoRa radio** *(optional, off-grid chat)*<br><img src="docs/assets/hardware/LORA_chip_with_433hz_antenna.png" width="240"> | Chat with FLORA from outside Wi-Fi range over a LoRa mesh. | Optional. Heltec / LilyGo boards with 433 / 868 / 915 MHz antennas all work. Skip if you only need the web UI. |

**Minimum testing build** (just to play with the dashboard on a desk):
> 1 × Pi · 1 × ADS1115 · 1 × moisture sensor · 1 × USB camera. That's it. No relays, no pumps, no Hailo. Use the **"+ Add sensors"** button in the dashboard once it's up.

---

## 🚀 Quick start (Raspberry Pi)

```bash
git clone https://github.com/darkphantom-gamer/AIgriculture.git
cd AIgriculture

# 1) System packages (one-time)
sudo apt update
sudo apt install -y python3-lgpio python3-pip i2c-tools mariadb-server
sudo raspi-config nonint do_i2c 0          # enable I2C

# 2) Python deps
pip install -r requirements.txt --break-system-packages

# 3) Configure
cp .env.example .env                       # then EDIT .env (admin user/pass, API keys)
cp config.example.yaml config.yaml         # then EDIT config.yaml (SMTP for email alerts)
cp wiring.example.yaml wiring.yaml         # ONLY if you changed default pins

# 4) Run — pick ONE entry point
python main.py                              # CPU build (default)
# python main-hailo.py                      # Hailo build (only if HAT is plugged in)

# Enable security camera with frame-skip CPU YOLO (or HEF on Hailo):
python main.py --security-cam /dev/video0
```

Open `http://<pi-ip>:8000` and log in with the `ADMIN_USER` / `ADMIN_PASS` you set in `.env`.

> **Running on a laptop / non-Pi?** Use `main.py` (the CPU build). GPIO and I²C silently no-op when the hardware isn't there — you get the full dashboard, AI chat, and (USB / network) cameras. Skip step 1 entirely; just `pip install -r requirements.txt` and `python main.py`.

### Database

The default config talks to MariaDB / MySQL on `localhost:3306`. After `sudo apt install mariadb-server`, create a user + database to match your `.env`:

```bash
sudo mysql -e "CREATE DATABASE plantmonitor;
               CREATE USER 'plantmonitor'@'localhost' IDENTIFIED BY 'CHANGE-ME';
               GRANT ALL ON plantmonitor.* TO 'plantmonitor'@'localhost';
               FLUSH PRIVILEGES;"
```

Set `DB_USER`, `DB_PASS`, `DB_NAME` in `.env` to match. The app creates its tables automatically on first run.

### Run on boot (optional)

```bash
sudo tee /etc/systemd/system/aigriculture.service > /dev/null <<EOF
[Unit]
Description=AIgriculture
After=network-online.target mariadb.service
Wants=network-online.target

[Service]
Type=simple
User=pi
WorkingDirectory=/home/pi/AIgriculture
ExecStart=/usr/bin/python3 /home/pi/AIgriculture/main.py --security-cam /dev/video0
Restart=on-failure

[Install]
WantedBy=multi-user.target
EOF
sudo systemctl enable --now aigriculture
```

---

## 🔑 You MUST add your own credentials

**Nothing in this repo contains real API keys, passwords, or emails — that's by design.**
After `cp .env.example .env`, open `.env` and fill in your own:

| In `.env` | What to put | Where to get it |
|-----------|-------------|-----------------|
| `ADMIN_USER` | The dashboard username you want | (you choose) |
| `ADMIN_PASS` | A strong password | (you choose) — if left blank, a random one prints on first boot |
| `DB_USER` / `DB_PASS` / `DB_NAME` | MariaDB / MySQL creds | (your choice — see Database section) |
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

Default pin map (matches what `main.py` ships with):

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
python main.py                          # picks up wiring.yaml on startup
```

`wiring.yaml` lets you remap any pin, flip active-high/active-low, change buzzer count or frequency, and recalibrate moisture sensors — all without touching code.

---

## 💧 Irrigation

Burst irrigation, one pump per plant — run it two ways:

- **Manual** — tap a plant card on the dashboard **Overview** tab to pulse that plant's pump on demand.
- **Auto-mode** — the app watches each moisture sensor and waters on its own: it starts a burst when soil drops to **45 %**, stops at **65 %**, and **hard-locks** the pump if a reading ever crosses **70 %**, so a stuck sensor can never flood a plant.

Each plant maps to one relay channel and one moisture sensor (see [Wiring](#-wiring-change-one-file-to-match-your-board)). Pumps switch through the opto-isolated relay board — the Pi only drives the relay, never the pump current. Start with a single plant and grow the farm at runtime with [**+ Add sensors**](#-add-more-sensors-at-runtime); FLORA can also water, stop, and schedule any plant by name.

---

## Dashboard

![Dashboard status](docs/assets/dashboard_status.png)

Five tabs: **Overview** (live moisture + pump control), **Cameras** (MJPEG streams), **FLORA** (AI chat), **Events** (alert log), **Settings** (notifications + siren).

---

## Security camera

![Security camera result](docs/assets/Security_camera_result.png)

Frame-skip inference (every Nth frame) with a class allow-list keeps CPU usage low. On threat detection, the siren arms for 8 seconds and a snapshot is saved.

---

## FarmMonitor

![Farm Monitor architecture](docs/assets/Farm_Monitor_Core_Architecture.png)

Runs scheduled full-field scans. Captures a batch of frames, filters blurry ones, then runs disease and ripeness detection.

![Farm Monitor result](docs/assets/Farm_Monitor_Result.png)

Results are saved to `runtime/farmmonitor/` as JSON + JPEG. If disease is detected and SMTP is configured, an email alert is sent.

---

## Storage

![Storage](docs/assets/Storage_Data_screenshot.png)

All captured frames, farm scans, and security snapshots are browsable from the dashboard Events tab and the storage API.

---

## ➕ Add more sensors at runtime

The dashboard has a **"+ Add sensors"** button (top-right of the overview tab, admin-only). Click it and the app:

1. Scans the I²C bus across all 4 ADS1115 addresses (`0x48`-`0x4B`) × 4 channels each.
2. Finds channels with a plausible moisture reading that aren't already in use.
3. Registers them as new plants (letters `i`-`p`, up to 16 total) and persists them to `.plants.json`.
4. Starts polling them immediately — no restart, no code edits.

Useful when you start with the 2-sensor testing build and expand later.

---

## Camera options

Both the **security camera** and the **FarmMonitor camera** (disease / ripeness scans) accept the same source forms — RPi CSI, USB, RTSP IP cam, or HTTP-MJPEG. You pick the source per-camera with a CLI flag or an env var.

| Camera | CLI flag | Env var |
|--------|----------|---------|
| Security cam (intrusion) | `--security-cam <SRC>` | `SECURITY_CAMERA_SOURCE` |
| FarmMonitor (disease/ripeness) | `--farm-cam <SRC>` | `FARM_MONITOR_CAMERA` |
| RPi CSI shortcut (FarmMonitor only) | `--use-rpicam` | — |

```bash
# Raspberry Pi CSI camera — security only
python main.py --security-cam rpi

# Raspberry Pi CSI camera — FarmMonitor (picamera2 path)
python main.py --use-rpicam

# Raspberry Pi CSI camera — FarmMonitor (OpenCV path, no picamera2 needed)
python main.py --farm-cam rpi

# USB camera, one each
python main.py --security-cam /dev/video0 --farm-cam /dev/video1

# IP / RTSP camera on either side
python main.py --security-cam rtsp://user:pass@192.168.1.10/live
python main.py --farm-cam   rtsp://user:pass@192.168.1.10/live

# HTTP-MJPEG IP camera (the same URL feeds both cameras for hardware-free testing)
python main.py --security-cam http://camera.example/cam.cgi \
               --farm-cam   http://camera.example/cam.cgi

# Mix and match: USB security cam + IP FarmMonitor cam (e.g. greenhouse cam)
python main.py --security-cam /dev/video0 \
               --farm-cam   rtsp://greenhouse:5554/live
```

Source strings accepted by **both** flags: `rpi` / `csi` (RPi CSI via OpenCV), `/dev/videoN` (USB), an integer (camera index), `rtsp://…` (IP RTSP), `http://…` (IP MJPEG). No code edits needed for new cameras — just change the flag or env.

Run **with no camera at all** to test the dashboard, FLORA, irrigation logic, and sensor expansion:

```bash
python main.py            # security cam off; FarmMonitor will log "no camera"
```

---

## 🧠 Plug in your own ML models (any crop, not just strawberry)

AIgriculture is crop-agnostic. Train YOLOv8 on whatever you grow — tomatoes, mangoes, peppers, lettuce, grapes — drop the weights into `Models/`, point an env var at them, and you're done. No code changes.

```bash
# 1. Drop your trained weights into Models/
cp my_tomato_disease.pt    Models/Tomato_disease.pt
cp my_tomato_ripeness.pt   Models/Tomato_ripeness.pt

# 2. Tell AIgriculture to use them (in .env, or inline)
DISEASE_MODEL_PATH=Models/Tomato_disease.pt \
RIPENESS_MODEL_PATH=Models/Tomato_ripeness.pt \
python main.py
```

For class names + display colors, duplicate the bundled label JSONs:

```bash
cp farm_monitor_disease_labels.json    farm_monitor_tomato_disease_labels.json
cp farm_monitor_ripeness_labels.json   farm_monitor_tomato_ripeness_labels.json
# Edit the JSONs to match your model's class names, then point at them:
DISEASE_LABELS_PATH=farm_monitor_tomato_disease_labels.json \
RIPENESS_LABELS_PATH=farm_monitor_tomato_ripeness_labels.json \
python main.py
```

For the **security camera**, the CPU build uses any Ultralytics-compatible weight (`SECURITY_MODEL=Models/yolov8m.pt`, etc.). The Hailo build (`main-hailo.py`) takes a `.hef` model — point `PLANTWATCH_SECURITY_HEF` at your file in `Models/`.

The bundled `Disease_detect.pt` and `Ripeness_detect.pt` are tuned for strawberries — they're a starting point, not a hard requirement.

---

## Hailo (optional accelerator)

The default CPU path (`main.py`) works on every Pi 4 / 5. If you have a **Hailo-10H AI HAT**, install HailoRT and Hailo Apps on the host first, then run the Hailo build:

```bash
python main-hailo.py --security-cam /dev/video0
```

`main-hailo.py` shares 100% of the dashboard, login, FLORA, FarmMonitor, irrigation, Meshtastic, storage, and email-alert code with `main.py`. The only difference is that the security-camera inference runs on the Hailo HEF model instead of CPU YOLO — usually ~10× faster.

If the HAT isn't actually plugged in, `main-hailo.py` logs a warning and keeps everything else running. You can switch between the two scripts at any time without touching configs or the database.

---

## CLI reference

```
python main.py [options]            # CPU build (default)
python main-hailo.py [options]      # Hailo HAT build

  --security-cam SRC  camera for intrusion detection
                      rpi | csi | /dev/videoN | <index> | rtsp://… | http://…
  --farm-cam     SRC  camera for FarmMonitor (disease / ripeness scans)
                      rpi | csi | /dev/videoN | <index> | rtsp://… | http://…
  --use-rpicam        use the picamera2 (libcamera) capture path for FarmMonitor
```

Environment knobs (see `.env.example`):
- `SECURITY_FRAME_SKIP` (default 5), `SECURITY_IMGSZ` (default 640),
  `SECURITY_MODEL` (default `yolov8s.pt` — swap for `yolov8n.pt` for max FPS,
  or `yolov8m.pt` for even higher recall).
- `FARM_MONITOR_CAMERA` — `/dev/videoN`, `rpi`, `rtsp://…`, `http://…`, or
  blank to auto-detect a USB cam.
- `DISEASE_MODEL_PATH` / `RIPENESS_MODEL_PATH` — point at any YOLOv8 `.pt`
  inside `Models/` to switch crops without code edits.
- `DISEASE_LABELS_PATH` / `RIPENESS_LABELS_PATH` — point at custom label JSONs
  (see the bundled `farm_monitor_*_labels.json` for the format).
- `PLANTWATCH_SECURITY_HEF` — Hailo HEF model for the Hailo build.

---

## FLORA AI assistant
*Farm Live Operation and Reasoning Assistant*

![FLORA preview](docs/assets/FLORA_preview.jpeg)

FLORA is the chat tab in the dashboard — but it doesn't only answer, it actually acts on the farm. It understands natural-language commands:

- *"Water plant A"* → triggers burst irrigation
- *"What is the moisture level of all plants?"* → reads all sensors
- *"Stop the pump on C"* → stops pump C
- *"Is there any disease detected?"* → checks the latest FarmMonitor scan

Every capability below is wired to a real tool that touches sensors, relays, cameras, the event database, or the email queue. When no cloud LLM is reachable, FLORA falls back to deterministic keyword routing — so every capability keeps working offline.

### Capabilities

| Capability | What it does |
|------------|--------------|
| **Full farm analysis** | Live moisture, pump state, sensor health, security camera state, and FarmMonitor camera read-out for every active plant — on demand. |
| **History queries** | *"What happened last week?"*, *"show disease detections in the past 3 days"* — answered from the event database for as long as the events are kept. |
| **Irrigation control** | Start or stop watering on any plant individually — *"water plant C"*, *"stop pump B"*. |
| **Guard control** | Arm or disarm the security camera + dual-buzzer siren — *"guard on"*, *"I'm leaving"*, *"I'm back"*. |
| **FarmMonitor scans** | Trigger plant-health and harvest-readiness scans on demand — *"scan now"*, *"check the strawberries"*. |
| **Email** | Send detection photos, scan results, or report attachments straight to the configured operator address. |
| **PDF reports** | Generate a downloadable PDF of farm state and (optionally) email it on the same call. |
| **Scheduling** | Schedule any of the above for later — *"water plant A in 2 hours"*, *"scan every morning at 6"*. |
| **Cloud or offline** | Cloud mode uses any one of Groq / Cerebras / Mistral / Gemini for natural-language understanding. Offline mode uses deterministic keyword routing — every capability above still works. |

### Architecture

FLORA runs as three cooperating layers:

| Layer | Role |
|-------|------|
| ![Layer 1](docs/assets/FLORA_first_layer_Architecture.png) | Provider routing + fallback |
| ![Layer 2](docs/assets/FLORA_Second_layer_Architecture.png) | Tool dispatch (sensors, pumps, camera, scheduler) |
| ![Layer 3](docs/assets/FLORA_Third_Lasyer_Architecture.png) | FLORA reasoning and integration |

---

## 📡 Meshtastic LoRa bridge

Chat with FLORA from outside Wi-Fi range, over a LoRa mesh — completely off-grid. Set `MESH_ENABLED=true` in `.env` and point `MESH_HOST` at your node; FLORA listens on any channel or DM and replies only to the sender.

<p align="center">
  <img src="docs/img/meshtastic-flora-proof.jpg" alt="FLORA replying over a real LoRa mesh" width="520">
</p>

Both `main.py` and `main-hailo.py` start the Meshtastic ↔ FLORA bridge **in the same process** — no second service to run. The bridge:

- Connects to a local `meshtasticd` over TCP (default `localhost:4403`)
- Listens on any channel or DM
- Forwards messages to FLORA via the in-process HTTP API
- Replies to the sender on the same channel the request arrived on

If the Meshtastic library isn't installed or the connection drops, the bridge logs a warning and `main.py` keeps running — it never blocks the dashboard. See `.env.example` for the full set of `MESH_*` knobs (allowed nodes, reply mode, channel filter).

### Core architecture

![Meshtastic](docs/assets/MEshtastic.png)

---

## Project layout

```
AIgriculture/
├── main.py                             # CPU build: dashboard + sensors + irrigation + CPU YOLO
├── main-hailo.py                       # Hailo build: same as main.py + Hailo HEF security cam
│
├── design/                             # ── front-end pages (theme + UI) ──
│   ├── dashboard.html                  # the dashboard (single-page app)
│   └── login.html                      # login screen
│
├── assets/                             # ── static images / audio served by the dashboard ──
│   ├── farmer.png                      # default user avatar
│   ├── low-cortisol.png                # mood / wellness card image
│   ├── test_drive_avatar.png           # demo avatar
│   ├── agrisense-favicon.svg           # favicon
│   └── threat.mp3                      # siren sound
│
├── Models/                             # ── ML weights (swap for any crop) ──
│   ├── Disease_detect.pt               # YOLOv8 disease detector (strawberry default)
│   ├── Ripeness_detect.pt              # YOLOv8 ripeness detector (strawberry default)
│   ├── Disease_detect.hef              # Hailo HEF for disease (optional, Hailo build)
│   └── yolov8*.pt                      # auto-downloaded security weights (gitignored)
│
├── farm_monitor_designer_email.py      # branded alert email composer
├── farm_monitor_pt_scan.py             # disease + ripeness .pt scanner
├── farm_monitor_disease_labels.json    # YOLO class labels for disease
├── farm_monitor_ripeness_labels.json   # YOLO class labels for ripeness
├── flora_agent.py / flora_config.py    # FLORA AI assistant
├── flora_report.py / flora_scheduler.py / flora_tools.py
├── meshtastic_flora_bridge.py          # LoRa bridge
│
├── docs/assets/                        # images used in this README
├── docs/{ja,hi,ru,zh}/README.md        # translated READMEs
│
├── .env.example                        # ← copy to .env and edit
├── config.example.yaml                 # ← copy to config.yaml and edit (for email)
├── wiring.example.yaml                 # ← copy to wiring.yaml and edit (for custom pins)
└── requirements.txt
```

Everything in `design/`, `assets/`, and `Models/` is **swappable**. Override
paths via env (`DISEASE_MODEL_PATH`, `RIPENESS_MODEL_PATH`, `DISEASE_LABELS_PATH`,
`RIPENESS_LABELS_PATH`) or just drop new files in place with the same names.

---

## Author

**The Great Himkamal** ([@darkphantom-gamer](https://github.com/darkphantom-gamer))
Built and maintained on real hardware — a strawberry farm running on a Raspberry Pi 5.
Contributions, crop models, and translations welcome.

---

## License

MIT — see [LICENSE](LICENSE).
