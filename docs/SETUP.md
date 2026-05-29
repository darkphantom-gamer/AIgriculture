# Setup Guide

A plug-and-play guide for AIgriculture on a Raspberry Pi. This document is a
quick reference — the top-level [`README.md`](../README.md) has the full
explanation of every section.

## Prerequisites

| | Minimum |
|---|---|
| Hardware | Raspberry Pi 4 / 5 (2 GB+ RAM) |
| OS | Raspberry Pi OS Bookworm (64-bit) |
| Python | The **native** Python 3 that ships with Bookworm (`/usr/bin/python3`, 3.11+). No pyenv, no conda, no separate 3.11 install — just the one that comes with the OS. |
| Optional | Hailo-10H AI HAT (only if you want hardware-accelerated vision) |

---

## Quick start

```bash
git clone https://github.com/darkphantom-gamer/AIgriculture.git
cd AIgriculture

# 1) System packages (one-time)
sudo apt update
sudo apt install -y python3-lgpio python3-pip i2c-tools mariadb-server
sudo raspi-config nonint do_i2c 0          # enable I2C

# 2) Python deps (use the native python3 that ships with Bookworm)
pip install -r requirements.txt --break-system-packages

# 3) Configure
cp .env.example .env                       # then EDIT .env (admin user/pass, API keys)
cp config.example.yaml config.yaml         # then EDIT config.yaml (SMTP for email alerts)
cp wiring.example.yaml wiring.yaml         # ONLY if you changed default pins

# 4) Pick ONE entry point
python main.py                              # CPU build (default — runs on any Pi)
# python main-hailo.py                      # Hailo build (only if HAT is plugged in)

# Optional: enable the security camera
python main.py --security-cam /dev/video0
```

Open `http://<pi-ip>:8000` and log in with `ADMIN_USER` / `ADMIN_PASS` from `.env`.

> **No real Pi at hand?** `main.py` runs on a laptop too. GPIO and I²C silently
> no-op when the hardware isn't there; the dashboard, FLORA chat, and (USB /
> network) cameras still work.

---

## Two entry points

| Script | When to use | Security-camera engine |
|--------|-------------|------------------------|
| `python main.py` | Default. Any Raspberry Pi 4 / 5 or laptop. | Ultralytics YOLOv8n on CPU with frame-skip. |
| `python main-hailo.py` | You have the Hailo-10H AI HAT installed. | Hailo HEF pipeline — ~10× faster. |

Everything else (dashboard, login, FLORA, FarmMonitor, irrigation, email alerts,
storage, Meshtastic) is **identical** between the two.

---

## Environment variables (`.env`)

Copy `.env.example` to `.env` and fill in your values.

| Variable | Required | Description |
|----------|----------|-------------|
| `ADMIN_USER` | yes | Dashboard admin username |
| `ADMIN_PASS` | yes | Dashboard admin password (auto-generated and printed on first boot if blank) |
| `JWT_SECRET` | no | Random string for JWT signing (auto-generated if blank) |
| `DB_HOST` / `DB_PORT` / `DB_USER` / `DB_PASS` / `DB_NAME` | yes | MariaDB / MySQL credentials |
| `GROQ_API_KEY` | no | FLORA AI via Groq (recommended, fast, free tier) |
| `CEREBRAS_API_KEY` | no | FLORA AI via Cerebras |
| `MISTRAL_API_KEY` | no | FLORA AI via Mistral |
| `GEMINI_API_KEY` | no | FLORA AI via Gemini |
| `MESH_ENABLED` | no | Set `true` to enable the in-process Meshtastic LoRa bridge |
| `MESH_HOST` | no | Host of your `meshtasticd` (default `localhost`) |
| `MESH_ALLOWED_NODES` | no | Comma-separated node IDs that FLORA responds to |
| `SECURITY_FRAME_SKIP` | no | CPU YOLO frame-skip (default `5`; lower = snappier, higher CPU) |
| `SECURITY_IMGSZ` | no | CPU YOLO input size (default `480`) |
| `PLANTWATCH_SECURITY_HEF` | no | Path to a Hailo `.hef` model (only used by `main-hailo.py`) |

FLORA works fully **offline** (deterministic keyword routing) when no API keys
are configured. It also auto-falls-back to offline when the Pi has no
internet — no cloud round-trip means no waiting.

---

## Database

The app uses **MariaDB / MySQL**.

```bash
sudo apt install -y mariadb-server
sudo mysql -e "CREATE DATABASE plantmonitor;
               CREATE USER 'plantmonitor'@'localhost' IDENTIFIED BY 'CHANGE-ME';
               GRANT ALL ON plantmonitor.* TO 'plantmonitor'@'localhost';
               FLUSH PRIVILEGES;"
```

Then set `DB_USER`, `DB_PASS`, `DB_NAME` in `.env` to match. The app creates
its tables automatically on first run.

To reset accounts:

```bash
sudo mysql -e "TRUNCATE TABLE plantmonitor.users;"
# restart the app — the admin account is reseeded from ADMIN_USER/ADMIN_PASS
```

---

## Camera selection

| Spec | Example | Description |
|------|---------|-------------|
| `csi:N` | `csi:0` | Raspberry Pi CSI camera (picamera2) |
| `/dev/videoN` | `/dev/video0` | USB camera |
| `rtsp://...` | `rtsp://192.168.1.10/stream` | Network / IP camera |

Flags on `main.py` / `main-hailo.py`:

```bash
python main.py \
  --security-cam /dev/video0 \
  --farm-cam     rtsp://192.168.1.10/live
```

One camera is enough to start — just pass `--security-cam` and skip the other.

---

## Wiring overview

Default pin map (matches what `main.py` ships with):

| Component | Default BCM pins |
|-----------|------------------|
| Pump relays (Plant A → H) | `17, 27, 22, 23, 5, 6, 13, 19` (active LOW) |
| Buzzer siren | `18, 12` (2700 Hz) |
| Moisture sensors | ADS1115 × 2 at I²C `0x48` and `0x49` |
| I²C bus | `/dev/i2c-1` |
| GPIO chip | `/dev/gpiochip0` (auto-tries `4` for Pi 5 if 0 fails) |

To use different pins, copy `wiring.example.yaml` to `wiring.yaml` and edit —
no Python changes required.

---

## Hailo (optional)

Install HailoRT on the host first (Raspberry Pi 5 + Hailo-10H AI HAT), then:

```bash
pip install -r requirements.txt --break-system-packages
PLANTWATCH_SECURITY_HEF=/path/to/yolov8.hef python main-hailo.py --security-cam /dev/video0
```

If the HAT is not plugged in, `main-hailo.py` falls back gracefully and warns
in the log. For Pi without the HAT, use `python main.py` (the CPU build).

---

## Meshtastic LoRa bridge (in-process)

`main.py` and `main-hailo.py` both start the Meshtastic ↔ FLORA bridge in the
same process when `MESH_ENABLED=true`. No separate service to run.

```bash
# In .env
MESH_ENABLED=true
MESH_HOST=localhost
MESH_ALLOWED_NODES=        # blank = allow all
```

The bridge connects to a local `meshtasticd` over TCP, listens on any channel
or DM, forwards to FLORA, and replies on the same channel that the request
arrived on. See [`../README.md`](../README.md) for the screenshot of FLORA
replying over a real LoRa mesh.

---

## Run on boot (optional)

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

Note `ExecStart` uses `/usr/bin/python3` — the **native** Pi Python (3.11+).
No virtualenv, no pyenv, no separate 3.11. Just the one that ships with
Raspberry Pi OS Bookworm.

---

## Troubleshooting

| Symptom | Fix |
|---------|-----|
| `[Errno 13] Permission denied: '/home/pi/AIgriculture/FarmMonitor_Work/...'` | The directory was created by another user (e.g. an old Docker run). Run `sudo chown -R pi:pi /home/pi/AIgriculture/FarmMonitor_Work`. The latest `main.py` also surfaces a clear error message that includes the exact `chown` command. |
| FLORA always falls back to offline | That's by design when the Pi has no internet — see the offline reachability probe in `flora_agent.py`. Plug in Wi-Fi / Ethernet and try again. |
| Dashboard at `/` shows nothing | Confirm there's no leftover Docker container on port 8000: `docker ps`. If yes, `docker rm -f <container>` and restart `main.py`. |
| `+ Add sensors` finds nothing | Without an ADS1115 on the I²C bus this is expected. The button still works — it just reports `available: []`. |
