# Setup Guide

## Prerequisites

| | Minimum |
|---|---|
| Hardware | Raspberry Pi 4 / 5 (2 GB+ RAM) |
| OS | Raspberry Pi OS Bookworm (64-bit) |
| Python | 3.11+ |
| Optional | Hailo-8 M.2 AI accelerator |

---

## Quick start — Docker (recommended)

```bash
git clone https://github.com/darkphantom-gamer/AIgriculture.git
cd AIgriculture
cp .env.example .env          # fill in secrets (see Environment Variables below)
docker compose up -d
```

Open `http://<pi-ip>:8000` in your browser.

**Default admin credentials** come from `.env` (`ADMIN_USER` / `ADMIN_PASS`).
Change them before exposing the dashboard to a network.

---

## Native install

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt

cp .env.example .env          # edit secrets
cp config.example.yaml config.yaml   # edit SMTP / thresholds (optional)

python -m aigriculture \
  --security-camera csi:0 \
  --farm-camera     csi:1
```

---

## Environment variables (`.env`)

Copy `.env.example` to `.env` and fill in your values.

| Variable | Required | Description |
|----------|----------|-------------|
| `ADMIN_USER` | yes | Dashboard admin username |
| `ADMIN_PASS` | yes | Dashboard admin password |
| `JWT_SECRET` | no | Random string for JWT signing (auto-generated if blank) |
| `GROQ_API_KEY` | no | FLORA AI via Groq |
| `CEREBRAS_API_KEY` | no | FLORA AI via Cerebras |
| `MISTRAL_API_KEY` | no | FLORA AI via Mistral |
| `GEMINI_API_KEY` | no | FLORA AI via Gemini |
| `MESH_ENABLED` | no | Set `true` to enable Meshtastic LoRa bridge |
| `MESH_HOST` | no | IP of your Meshtastic node (TCP mode) |
| `MESH_ALLOWED_NODES` | no | Comma-separated node IDs that FLORA responds to |

FLORA works offline (keyword rules) when no API keys are provided.

---

## Camera selection (`--camera` flags)

| Spec | Example | Description |
|------|---------|-------------|
| `csi:N` | `csi:0` | Raspberry Pi CSI camera (picamera2) |
| `/dev/videoN` | `/dev/video0` | USB camera |
| `rtsp://...` | `rtsp://192.168.1.10/stream` | Network / IP camera |

Pass `--security-camera` and `--farm-camera` independently:

```bash
python -m aigriculture \
  --security-camera /dev/video0 \
  --farm-camera     rtsp://192.168.1.10/live
```

---

## Hailo (optional)

Install HailoRT on the host first (see `models/README.md`), then:

```bash
pip install -r requirements-hailo.txt
python -m aigriculture --backend hailo
```

Or with Docker:

```bash
docker compose -f docker-compose.yml -f docker-compose.hailo.yml up -d
```

---

## Database

AIgriculture uses **SQLite** — no database server required.

The database file is created automatically at first startup:

```
runtime/aigriculture.db
```

It stores user accounts and login sessions only.
Sensor readings, storage events, and farm scan results are kept as
files in `runtime/` subdirectories.

To reset all accounts and sessions (keeps sensor data):

```bash
rm runtime/aigriculture.db
# restart the app — admin account is recreated from ADMIN_USER/ADMIN_PASS
```

---

## Wiring overview

See `aigriculture.txt` for the full pin map. Quick reference:

- **Moisture sensors** — ADS1115 ADC over I2C (`/dev/i2c-1`)
  - Board 1 (0x48): plants A–D on channels A0–A3
  - Board 2 (0x49): plants E–H on channels A0–A3
- **Relay board** — 8-channel, active LOW, BCM pins 17 27 22 23 5 6 13 19
- **Buzzers** — BCM pins 18 and 12 (2700 Hz siren)

Edit pin assignments in `aigriculture/hardware/gpio.py` if your wiring differs.

---

## Running as a systemd service

```ini
# /etc/systemd/system/aigriculture.service
[Unit]
Description=AIgriculture farm dashboard
After=network.target

[Service]
User=pi
WorkingDirectory=/home/pi/AIgriculture
EnvironmentFile=/home/pi/AIgriculture/.env
ExecStart=/home/pi/AIgriculture/.venv/bin/python -m aigriculture
Restart=on-failure

[Install]
WantedBy=multi-user.target
```

```bash
sudo systemctl daemon-reload
sudo systemctl enable --now aigriculture
```
