"""AIgriculture main app (CPU build) — dashboard, sensors, irrigation, cameras,
FLORA, mesh, and CPU YOLO intrusion detection.

This is the default build. It runs on a stock Raspberry Pi (or any Linux box)
with no Hailo HAT — the security camera uses Ultralytics YOLOv8n on CPU with
frame-skip for sane FPS. If you have the Hailo accelerator, use main-hailo.py
instead for hardware-accelerated detection.

Hardware pins live in wiring.yaml. Credentials and tunables live in .env and
config.yaml. See README.md for the full setup walkthrough.

Run:  python main.py
"""

import os, sys, time, threading, json, struct, asyncio, smtplib, re, hashlib, subprocess, shutil
import html as html_lib
from pathlib import Path
from datetime import datetime
from email.message import EmailMessage
from contextlib import asynccontextmanager
from urllib.parse import urlparse


def _load_env_file() -> None:
    """Load `.env` (next to main.py) into os.environ so `python main.py` Just Works.

    The README promises "edit .env then python main.py" — but without this
    loader, FastAPI / our os.getenv() calls below see an empty environment and
    every secret looks unset (you get the misleading `using password: NO`
    MariaDB error even when DB_PASS is filled in). We don't pull in
    python-dotenv: tiny KEY=VALUE parser is enough and keeps requirements
    lean.

    Blank-valued lines like ``PLANTWATCH_STORAGE=`` are SKIPPED instead of
    setting the key to an empty string — otherwise an empty value would shadow
    code-side defaults (e.g. ``STORAGE_PATH = Path(os.getenv("PLANTWATCH_STORAGE",
    str(BASE_DIR / "Storage_Data")))`` would resolve to ``Path("")`` → ``.``).
    """
    env_path = Path(__file__).resolve().parent / ".env"
    if not env_path.exists():
        return
    try:
        for raw in env_path.read_text(encoding="utf-8").splitlines():
            line = raw.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            key, _, value = line.partition("=")
            key = key.strip()
            if not key or key in os.environ:
                continue  # already set in the real environment — that wins
            value = value.strip()
            # Strip a single matching pair of surrounding quotes.
            if len(value) >= 2 and value[0] == value[-1] and value[0] in ("'", '"'):
                value = value[1:-1]
            if value == "":
                continue  # don't shadow defaults with empty strings
            os.environ[key] = value
    except OSError:
        pass


_load_env_file()

os.environ["GST_PLUGIN_FEATURE_RANK"] = "vaapidecodebin:NONE"

# Stream performance defaults for Pi 5 + USB camera. These do not change
# detection logic; they only prevent MJPEG/web clients from creating backlog.
STREAM_TARGET_FPS = float(os.getenv("PLANTWATCH_STREAM_FPS", "6"))
STREAM_JPEG_QUALITY = int(os.getenv("PLANTWATCH_JPEG_QUALITY", "62"))
PIPELINE_DEFAULT_WIDTH = os.getenv("PLANTWATCH_WIDTH", "640")
PIPELINE_DEFAULT_HEIGHT = os.getenv("PLANTWATCH_HEIGHT", "480")
PIPELINE_DEFAULT_FPS = os.getenv("PLANTWATCH_FPS", "7")
SECURITY_HEF_PATH = os.getenv(
    "PLANTWATCH_SECURITY_HEF",
    "/usr/local/hailo/resources/models/hailo10h/yolov8m.hef",
)


# ── Vision (CPU) ──────────────────────────────────────────────────────────────
# CPU build: no Hailo, no GStreamer. OpenCV handles capture + drawing,
# Ultralytics handles YOLOv8 detection. Both are pure-Python wheels.
try:
    import cv2
except ImportError:
    cv2 = None  # type: ignore
    print("[WARN] OpenCV not installed — security camera and farm-monitor preview disabled")


class _StdLogger:
    """Tiny print-based logger. Variable kept named `hailo_logger` so the rest
    of the file (status banner, info lines, error paths) stays untouched."""
    def info(self, m):    print(f"[INFO] {m}")
    def warning(self, m): print(f"[WARN] {m}")
    def error(self, m):   print(f"[ERR]  {m}")


hailo_logger = _StdLogger()

# ── picamera2 (optional — used with --use-rpicam flag) ────────────────────────
try:
    from picamera2 import Picamera2 as _Picamera2
    _PICAMERA2_AVAILABLE = True
except ImportError:
    _Picamera2 = None  # type: ignore
    _PICAMERA2_AVAILABLE = False

# ── Optional wiring.yaml — change GPIO/I2C without editing source ────────────
# Drop a wiring.yaml next to main.py (or set $WIRING_FILE) to override
# relay pins, ADS1115 addresses, calibration, and buzzer pins. Anything left
# out falls back to the default values defined further below, so the file is
# entirely optional.
_HERE = Path(__file__).resolve().parent
def _load_wiring_overrides():
    cand = []
    if os.getenv("WIRING_FILE"):
        cand.append(Path(os.environ["WIRING_FILE"]))
    cand += [_HERE / "wiring.yaml", Path.cwd() / "wiring.yaml"]
    try:
        import yaml as _yaml
    except ImportError:
        return {}
    for p in cand:
        if p.is_file():
            try:
                data = _yaml.safe_load(p.read_text(encoding="utf-8")) or {}
                print(f"[INFO] wiring overrides loaded from {p}")
                return data if isinstance(data, dict) else {}
            except Exception as e:
                print(f"[WARN] could not parse wiring file ({p}): {e}")
                return {}
    return {}
_WIRING_OVERRIDES = _load_wiring_overrides()

# ── GPIO ───────────────────────────────────────────────────────────────────────
# PLANTS is a *mutable* list. The dashboard's `+ Add sensors` button extends
# it at runtime when new ADS1115 chips are wired in. PUMP_PLANTS stays a
# subset that has an actual relay pin (sensor-only plants are not pumped).
PLANTS = list("abcdefgh")
PUMP_PLANTS = list("abcdefgh")

# ── Plant registry: which plants are ACTIVE vs reserved ──────────────────────
# All eight relay/sensor pins stay reserved in hardware; ACTIVE_PLANTS controls
# which ones the dashboard shows and counts. Defaults to 2 plants (A, B) and can
# be changed at runtime via /api/plants/{id}/enable|disable (no restart).
_PLANTS_FILE = Path(__file__).with_name(".plants.json")
PLANT_NAMES = {p: f"Plant {p.upper()}" for p in PLANTS}

# Stash of extra (i.j.k…p) sensor registrations the user wired in at runtime.
# Loaded here so they can be applied AFTER all per-plant dicts are defined.
_PENDING_EXTRA_PLANTS: dict = {}

def _load_plant_registry():
    global _PENDING_EXTRA_PLANTS
    active = ["a", "b"]
    try:
        data = json.loads(_PLANTS_FILE.read_text(encoding="utf-8"))
        # Extras get re-registered later (right after per-plant dicts exist).
        extras = data.get("extras") or {}
        if isinstance(extras, dict):
            _PENDING_EXTRA_PLANTS = {
                p: dict(v) for p, v in extras.items()
                if isinstance(p, str) and isinstance(v, dict)
            }
            for p in _PENDING_EXTRA_PLANTS:
                if p not in PLANTS:
                    PLANTS.append(p)
            PLANTS.sort()
            PLANT_NAMES.update({p: f"Plant {p.upper()}" for p in PLANTS})
        act = [p for p in data.get("active", []) if p in PLANTS]
        if act:
            active = act
        for p, n in (data.get("names") or {}).items():
            if p in PLANT_NAMES and isinstance(n, str) and n.strip():
                PLANT_NAMES[p] = n.strip()
    except Exception:
        pass
    return active

ACTIVE_PLANTS = _load_plant_registry()

def _save_plant_registry():
    try:
        _PLANTS_FILE.write_text(
            json.dumps({
                "active": ACTIVE_PLANTS,
                "names": PLANT_NAMES,
                "extras": _PENDING_EXTRA_PLANTS,
            }, indent=2),
            encoding="utf-8")
    except Exception as _e:
        print(f"[WARN] could not save .plants.json: {_e}")

RELAY_PINS = (_WIRING_OVERRIDES.get("relays") or {}).get("pins") or {
    "a": 17, "b": 27, "c": 22, "d": 23,
    "e": 5, "f": 6, "g": 13, "h": 19,
}
RELAY_ACTIVE_LOW = bool((_WIRING_OVERRIDES.get("relays") or {}).get("active_low", True))   # Current relay board: LOW = ON, HIGH = OFF.
RELAY_ON_LEVEL = 0 if RELAY_ACTIVE_LOW else 1
RELAY_OFF_LEVEL = 1 if RELAY_ACTIVE_LOW else 0
RELAY_PIN_SUMMARY = " ".join(f"{pin}({plant.upper()})" for plant, pin in RELAY_PINS.items())
try:
    import lgpio as GPIO
    _gpio_handle = GPIO.gpiochip_open(0)
    for _pin in RELAY_PINS.values():
        GPIO.gpio_claim_output(_gpio_handle, _pin, RELAY_OFF_LEVEL)
    GPIO_AVAILABLE = True
    print(f"[INFO] GPIO relays initialized on BCM {RELAY_PIN_SUMMARY} "
          f"({'active LOW' if RELAY_ACTIVE_LOW else 'active HIGH'})")
except Exception as _ge:
    _gpio_handle = None
    GPIO_AVAILABLE = False
    print(f"[WARN] GPIO not available ({_ge})")

# ── Buzzers (dual passive, synchronized intruder siren) ──────────────────────
# Security-camera-only, guard-active-only. ONE fixed tone for every threat.
# Passive buzzers need a PWM tone (not plain HIGH), driven via lgpio.tx_pwm.
BUZZER_PINS   = list((_WIRING_OVERRIDES.get("buzzers") or {}).get("pins", [18, 12]))   # BCM — free + PWM-capable (relays use 5,6,13,17,19,22,23,27; I2C 2,3)
BUZZER_FREQ   = int((_WIRING_OVERRIDES.get("buzzers") or {}).get("freq_hz", 2700))       # Hz warning tone (same for any threat)
BUZZER_ON_S   = float((_WIRING_OVERRIDES.get("buzzers") or {}).get("on_s", 0.25))       # beep duration
BUZZER_OFF_S  = float((_WIRING_OVERRIDES.get("buzzers") or {}).get("off_s", 0.20))      # gap between beeps
siren_enabled = True       # master mute (admin / FLORA can toggle)
_siren_on     = False      # set True only by the security-camera threat hook
_siren_lock   = threading.Lock()
try:
    if GPIO_AVAILABLE and _gpio_handle is not None:
        for _bp in BUZZER_PINS:
            GPIO.gpio_claim_output(_gpio_handle, _bp, 0)
        BUZZER_AVAILABLE = True
        print(f"[INFO] Buzzers ready on BCM {', '.join(str(p) for p in BUZZER_PINS)} "
              f"(passive, {BUZZER_FREQ} Hz)")
    else:
        BUZZER_AVAILABLE = False
        print("[WARN] Buzzers disabled (GPIO unavailable)")
except Exception as _be:
    BUZZER_AVAILABLE = False
    print(f"[WARN] Buzzers not available ({_be})")

def _buzzer_tone(on: bool):
    """Drive BOTH passive buzzers together (synchronized)."""
    if not BUZZER_AVAILABLE:
        return
    for _bp in BUZZER_PINS:
        try:
            GPIO.tx_pwm(_gpio_handle, _bp, BUZZER_FREQ if on else 0, 50 if on else 0)
        except Exception:
            pass

def _set_siren(on: bool):
    """Flip the siren flag from the per-frame detection hook (non-blocking)."""
    global _siren_on
    with _siren_lock:
        _siren_on = bool(on)

def _siren_loop():
    """Sound the fixed warning beep while the siren flag is set. Owns its own
    timing so the Hailo detection pipeline is never blocked."""
    sounding = False
    while True:
        try:
            with _siren_lock:
                active = _siren_on and siren_enabled and BUZZER_AVAILABLE
            if active:
                _buzzer_tone(True);  time.sleep(BUZZER_ON_S)
                _buzzer_tone(False); time.sleep(BUZZER_OFF_S)
                sounding = True
            else:
                if sounding:
                    _buzzer_tone(False)
                    sounding = False
                time.sleep(0.1)
        except Exception:
            try:
                _buzzer_tone(False)
            except Exception:
                pass
            time.sleep(0.5)

# ── ADS1115 / smbus2 ───────────────────────────────────────────────────────────
_M_OV         = _WIRING_OVERRIDES.get("moisture") or {}
ADS_ADDR      = int(_M_OV.get("ads_addr", 0x48))
ADS_ADDR_2    = int(_M_OV.get("ads_addr_2", 0x49))
REG_CONV      = 0x00
REG_CFG       = 0x01
DRY_VALUE     = int(_M_OV.get("dry_value", 17408))
WET_VALUE     = int(_M_OV.get("wet_value", 7569))
# Single-ended config words for A0..A3 — 128 SPS, ±4.096 V
MUX_CONFIGS   = [0xC1E3, 0xD1E3, 0xE1E3, 0xF1E3]
SENSOR_CHANNELS = {
    "a": (ADS_ADDR, 0), "b": (ADS_ADDR, 1), "c": (ADS_ADDR, 2), "d": (ADS_ADDR, 3),
    "e": (ADS_ADDR_2, 0), "f": (ADS_ADDR_2, 1), "g": (ADS_ADDR_2, 2), "h": (ADS_ADDR_2, 3),
}
try:
    import smbus2
    _bus = smbus2.SMBus(1)
    I2C_AVAILABLE = True
    print("[INFO] ADS1115 bus ready; probing sensors at 0x48 and optional 0x49")
except Exception as _ie:
    I2C_AVAILABLE = False
    print(f"[WARN] smbus2/ADS1115 not available ({_ie})")

# ── FastAPI ────────────────────────────────────────────────────────────────────
from fastapi import FastAPI, WebSocket, WebSocketDisconnect, Depends, Request, Form
from fastapi.responses import HTMLResponse, StreamingResponse, JSONResponse, RedirectResponse, Response
import uvicorn

# ── Auth / Security ────────────────────────────────────────────────────────────
import secrets as _secrets
from datetime import timedelta
try:
    import jwt as _jwt          # PyJWT
    JWT_AVAILABLE = True
except ImportError:
    JWT_AVAILABLE = False
    print("[WARN] PyJWT not installed — run: pip install PyJWT --break-system-packages")

try:
    # passlib 1.7.x probes ``bcrypt.__about__.__version__`` which was removed
    # in bcrypt 4.x — without this shim it logs a noisy AttributeError on every
    # boot even though hashing/verification still work. Stop the noise by giving
    # passlib the version string it expects.
    try:
        import bcrypt as _bcrypt_mod  # noqa: F401
        if not hasattr(_bcrypt_mod, "__about__"):
            class _BcryptAbout:  # tiny shim with just the attribute passlib reads
                __version__ = getattr(_bcrypt_mod, "__version__", "0.0.0")
            _bcrypt_mod.__about__ = _BcryptAbout()  # type: ignore[attr-defined]
    except ImportError:
        pass
    from passlib.context import CryptContext
    _pwd_ctx = CryptContext(schemes=["bcrypt"], deprecated="auto")
    BCRYPT_AVAILABLE = True
except ImportError:
    BCRYPT_AVAILABLE = False
    print("[WARN] passlib not installed — run: pip install passlib[bcrypt] --break-system-packages")

try:
    import pymysql, pymysql.cursors
    MYSQL_AVAILABLE = True
except ImportError:
    MYSQL_AVAILABLE = False
    print("[WARN] pymysql not installed — run: pip install pymysql --break-system-packages")

# ── Config ─────────────────────────────────────────────────────────────────────
BASE_DIR      = Path(__file__).resolve().parent
PROJECT_ROOT  = BASE_DIR.parent
STORAGE_PATH  = Path(os.getenv("PLANTWATCH_STORAGE", str(BASE_DIR / "Storage_Data")))
CONF_THRESH   = 0.45
TRIGGER_PCT   = 45.0    # auto irrigation trigger
STOP_PCT      = 65.0    # irrigation re-read target: stop once moisture reaches this
LOCK_PCT      = 70.0    # absolute hardlock — no pump may run at/above this
BURST_ON_S    = 3.0     # pump ON seconds per burst
BURST_WAIT_S  = 10.0    # soak/absorb pause between bursts
BURST_CLIMB_SKIP = 1.5  # %: if moisture rose >= this during the soak, skip the next burst
CMD_MAX_S     = 180.0   # safety cap on a commanded (manual/FLORA) burst session
SENSOR_POLL_S = 0.5     # sensor loop cadence
ADS_WAIT_S    = 0.009   # ADS1115 conversion wait, tuned for 128 SPS
ADS_WARN_S    = 300.0   # throttle repeated offline warnings; sensors may be unplugged during demos

# Farm Monitor owns the real plant camera. Security camera only uses a real
# camera when launched with --security-cam /dev/videoX.
SECURITY_CAMERA_SOURCE = ""
def _auto_detect_usb_camera(env_override: str = "") -> str:
    """Return first USB capture device (skips RPi CSI subdevs), or env_override/fallback."""
    if env_override:
        return env_override
    import subprocess as _sp, os as _os
    try:
        devs = sorted(
            f"/dev/{d}" for d in _os.listdir("/dev") if d.startswith("video")
        )
        for dev in devs:
            r = _sp.run(
                ["udevadm", "info", "--query=all", "--name=" + dev],
                capture_output=True, check=False, timeout=2,
            )
            out = r.stdout.decode("utf-8", errors="replace")
            if "ID_BUS=usb" in out and ":capture:" in out:
                return dev
    except Exception:
        pass
    return ""  # no USB camera found; do not steal the Pi CSI/security camera

def _extract_farm_cam_arg() -> str:
    """Pull `--farm-cam <source>` out of sys.argv (mirrors --security-cam).
    Accepts the same source strings as --security-cam:
      /dev/video0 (USB)  |  rtsp://… (IP)  |  http://… (MJPEG)  |  0 (index)  |  rpi/csi (CSI via OpenCV)
    """
    import sys as _sys
    cleaned = [_sys.argv[0]]
    source = ""
    i = 1
    while i < len(_sys.argv):
        arg = _sys.argv[i]
        if arg == "--farm-cam" and i + 1 < len(_sys.argv):
            source = _sys.argv[i + 1]
            i += 2
            continue
        if arg.startswith("--farm-cam="):
            source = arg.split("=", 1)[1]
            i += 1
            continue
        cleaned.append(arg)
        i += 1
    _sys.argv = cleaned
    return source

_farm_cam_cli = _extract_farm_cam_arg()
# Precedence: --farm-cam CLI flag  >  FARM_MONITOR_CAMERA env  >  USB auto-detect
FARM_MONITOR_CAMERA = _farm_cam_cli or _auto_detect_usb_camera(os.getenv("FARM_MONITOR_CAMERA", ""))
# --use-rpicam → CSI camera via picamera2 (FarmMonitor); CLI source overrides this.
USE_RPICAM: bool = (
    ("--use-rpicam" in __import__("sys").argv) and _PICAMERA2_AVAILABLE
    and not _farm_cam_cli
)
FARM_MONITOR_WIDTH = int(os.getenv("FARM_MONITOR_WIDTH", "2048"))
FARM_MONITOR_HEIGHT = int(os.getenv("FARM_MONITOR_HEIGHT", "1536"))
FARM_MONITOR_FPS = float(os.getenv("FARM_MONITOR_FPS", "7"))
FARM_MONITOR_JPEG_QUALITY = int(os.getenv("FARM_MONITOR_JPEG_QUALITY", "90"))
FARM_MONITOR_SATURATION = int(os.getenv("FARM_MONITOR_SATURATION", "72"))
FARM_MONITOR_CONTRAST = int(os.getenv("FARM_MONITOR_CONTRAST", "52"))
FARM_MONITOR_BRIGHTNESS = int(os.getenv("FARM_MONITOR_BRIGHTNESS", "0"))
FARM_MONITOR_BATCH_FRAMES = int(os.getenv("FARM_MONITOR_BATCH_FRAMES", "25"))
FARM_MONITOR_CAPTURE_GAP = float(os.getenv("FARM_MONITOR_CAPTURE_GAP", "0.3"))
FARM_MONITOR_SCAN_INTERVAL = float(os.getenv("FARM_MONITOR_SCAN_INTERVAL", str(6 * 60 * 60)))
FARM_MONITOR_SCAN_CYCLES = int(os.getenv("FARM_MONITOR_SCAN_CYCLES", "2"))
FARM_MONITOR_EVENT_RATIO = float(os.getenv("FARM_MONITOR_EVENT_RATIO", "0.50"))
FARM_MONITOR_DISEASE_CONF = float(os.getenv("FARM_MONITOR_DISEASE_CONF", os.getenv("FARM_MONITOR_CONF", "0.50")))
FARM_MONITOR_RIPENESS_CONF = float(os.getenv("FARM_MONITOR_RIPENESS_CONF", "0.25"))
FARM_MONITOR_BLUR_VAR = float(os.getenv("FARM_MONITOR_BLUR_VAR", "80"))
FARM_MONITOR_WORK = BASE_DIR / "FarmMonitor_Work"
FARM_MONITOR_SCAN_SCRIPT = BASE_DIR / "farm_monitor_pt_scan.py"


def _ensure_writable_dir(path, friendly_name: str = "directory") -> None:
    """Make ``path`` exist and be writable by us.

    Old installs sometimes left this directory owned by ``root`` (e.g. from a
    legacy Docker run). Raise a clear, fixable error instead of a bare
    ``[Errno 13] Permission denied`` further downstream.
    """
    try:
        path.mkdir(parents=True, exist_ok=True)
    except PermissionError as e:
        raise PermissionError(
            f"{friendly_name} '{path}' is not writable. "
            f"Run:  sudo chown -R $USER:$USER '{path}'  and retry."
        ) from e
    if not os.access(path, os.W_OK):
        try:
            os.chmod(path, 0o755)
        except OSError:
            pass
        if not os.access(path, os.W_OK):
            raise PermissionError(
                f"{friendly_name} '{path}' is not writable by the current user. "
                f"Run:  sudo chown -R $USER:$USER '{path}'  and retry."
            )
# ─── Crop models (swappable for any crop, not just strawberry) ─────────────────
# Drop your own YOLOv8 .pt files into Models/ and point these envs at them to
# scan any crop. Labels JSON maps class names to human-readable text + colors;
# duplicate farm_monitor_*_labels.json as a template for new crops.
_MODELS_DIR = BASE_DIR / "Models"
FARM_MONITOR_DISEASE_PT = Path(os.getenv(
    "DISEASE_MODEL_PATH", str(_MODELS_DIR / "Disease_detect.pt")
))
FARM_MONITOR_RIPENESS_PT = Path(os.getenv(
    "RIPENESS_MODEL_PATH", str(_MODELS_DIR / "Ripeness_detect.pt")
))
FARM_MONITOR_DISEASE_LABELS = Path(os.getenv(
    "DISEASE_LABELS_PATH", str(BASE_DIR / "farm_monitor_disease_labels.json")
))
FARM_MONITOR_RIPENESS_LABELS = Path(os.getenv(
    "RIPENESS_LABELS_PATH", str(BASE_DIR / "farm_monitor_ripeness_labels.json")
))


# ── CDN-style content hashing ──────────────────────────────────────────────────
# Public URLs intentionally expose only an opaque content hash, never the original
# asset or event filename. The original filename remains internal on disk.
HASH_LEN = 32
_OPAQUE_HASH_RE = re.compile(r"^(?P<hash>[0-9a-fA-F]{16,64})(?P<suffix>\.[A-Za-z0-9]+)$")
_LEGACY_NAMED_HASH_RE = re.compile(r"^(?P<stem>.+)\.(?P<hash>[0-9a-fA-F]{12,64})(?P<suffix>\.[A-Za-z0-9]+)$")
_ASSET_MEDIA = {
    ".png": "image/png", ".jpg": "image/jpeg", ".jpeg": "image/jpeg",
    ".gif": "image/gif", ".webp": "image/webp", ".svg": "image/svg+xml",
    ".mp3": "audio/mpeg",
}
_ASSET_HASH_CACHE = {}
_STORAGE_ALIAS_CACHE = {}


def _file_hash(path: Path, length: int = HASH_LEN) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()[:length]


def _opaque_hashed_filename(path: Path) -> str:
    return f"{_file_hash(path)}{path.suffix.lower()}"


def _strip_legacy_named_hash(filename: str) -> str:
    safe_name = Path(filename).name
    m = _LEGACY_NAMED_HASH_RE.match(safe_name)
    if not m:
        return safe_name
    return f"{m.group('stem')}{m.group('suffix').lower()}"


def _is_opaque_hashed_filename(filename: str) -> bool:
    return bool(_OPAQUE_HASH_RE.match(Path(filename).name))


def _asset_dir() -> Path:
    """Return the assets folder (preferred) or repo root for legacy layouts."""
    base = BASE_DIR / "assets"
    return base if base.is_dir() else BASE_DIR


def _asset_candidates():
    base = _asset_dir()
    return [p for p in base.iterdir() if p.is_file() and p.suffix.lower() in _ASSET_MEDIA]


def _asset_url(filename: str) -> str:
    safe_name = _strip_legacy_named_hash(filename)
    path = _asset_dir() / safe_name
    if not path.exists() or path.suffix.lower() not in _ASSET_MEDIA:
        return f"/img/{Path(filename).name}"
    return f"/img/{_opaque_hashed_filename(path)}"


def _resolve_opaque_asset(filename: str):
    safe_name = Path(filename).name
    m = _OPAQUE_HASH_RE.match(safe_name)
    if not m:
        return None
    hash_part = m.group('hash').lower()
    suffix = m.group('suffix').lower()
    key = (hash_part, suffix)
    cached = _ASSET_HASH_CACHE.get(key)
    if cached and cached.exists():
        return cached
    for candidate in _asset_candidates():
        if candidate.suffix.lower() != suffix:
            continue
        try:
            if _file_hash(candidate, len(hash_part)) == hash_part:
                _ASSET_HASH_CACHE[key] = candidate
                return candidate
        except OSError:
            continue
    return None


def _apply_content_hashed_assets(html: str) -> str:
    pattern = re.compile(r"/img/([A-Za-z0-9_.-]+\.(?:png|jpg|jpeg|gif|webp|svg|mp3))")
    def repl(match):
        name = match.group(1)
        if _is_opaque_hashed_filename(name):
            return match.group(0)
        return _asset_url(name)
    return pattern.sub(repl, html)


def _safe_label_filename(label: str) -> str:
    cleaned = re.sub(r"[^A-Za-z0-9_-]+", "_", str(label).strip()).strip("_").lower()
    return cleaned or "event"


def _public_storage_name(path: Path) -> str:
    # Every storage image exposed to the browser is hash-only, even if the file on
    # disk is an old named image such as person_detected.jpg.
    return _opaque_hashed_filename(path)


def _resolve_storage_image(folder: Path, filename: str):
    safe_name = Path(filename).name
    direct = folder / safe_name
    if direct.exists() and direct.suffix.lower() in (".jpg", ".jpeg", ".png"):
        return direct
    m = _OPAQUE_HASH_RE.match(safe_name)
    if not m:
        return None
    hash_part = m.group('hash').lower()
    suffix = m.group('suffix').lower()
    key = (str(folder), hash_part, suffix)
    cached = _STORAGE_ALIAS_CACHE.get(key)
    if cached and cached.exists():
        return cached
    for candidate in folder.iterdir():
        if not candidate.is_file() or candidate.suffix.lower() != suffix:
            continue
        try:
            if _file_hash(candidate, len(hash_part)) == hash_part:
                _STORAGE_ALIAS_CACHE[key] = candidate
                return candidate
        except OSError:
            continue
    return None

# ── Database / Auth config ─────────────────────────────────────────────────────
DB_HOST         = os.getenv("DB_HOST",     "localhost")
DB_PORT         = int(os.getenv("DB_PORT", "3306"))
DB_USER         = os.getenv("DB_USER",     "plantmonitor")
DB_PASS         = os.getenv("DB_PASS",     "")    # required — set in .env / docker-compose
DB_NAME         = os.getenv("DB_NAME",     "plantmonitor")

# JWT secret: prefer env var, fallback to a file-persisted random secret
_JWT_SECRET_FILE = Path(__file__).parent / ".jwt_secret"
def _load_jwt_secret() -> str:
    if "JWT_SECRET" in os.environ:
        return os.environ["JWT_SECRET"]
    if _JWT_SECRET_FILE.exists():
        return _JWT_SECRET_FILE.read_text().strip()
    s = _secrets.token_hex(48)
    try:
        _JWT_SECRET_FILE.write_text(s)
        _JWT_SECRET_FILE.chmod(0o600)
    except OSError as _e:
        print(f"[WARN] Cannot persist JWT secret ({_e}); using ephemeral — sessions reset on restart")
    return s

JWT_SECRET      = _load_jwt_secret()
JWT_ALGO        = "HS256"
JWT_EXPIRE_HRS  = 8

# Rate limiting (in-memory, per IP)
_rate_lock      = threading.Lock()
_rate_map: dict = {}          # ip -> {"count": int, "locked_until": float}
MAX_ATTEMPTS    = 5
LOCKOUT_SECS    = 15 * 60     # 15 minutes

FARM_THREATS = {"person","bird","cow","dog","horse","sheep","cat","elephant","bear","zebra"}

THREAT_LEVEL = {
    "person": "high", "bear": "high", "elephant": "high",
    "cow":    "med",  "horse": "med", "dog":     "med",
    "sheep":  "low",  "cat":  "low",  "zebra":   "low",  "bird": "low",
}
THREAT_EMOJI = {
    "person": "🧑", "bear": "🐻", "elephant": "🐘",
    "cow":    "🐄", "horse": "🐎", "dog":      "🐕",
    "sheep":  "🐑", "cat":  "🐈", "zebra":    "🦓",  "bird": "🐦",
}
COLORS = {
    "person":   (0,   0,   255), "bird":     (255, 0,   255),
    "cow":      (0,   165, 255), "dog":      (0,   255, 255),
    "horse":    (255, 165, 0  ), "sheep":    (0,   255, 128),
    "cat":      (128, 0,   255), "elephant": (255, 0,   0  ),
    "bear":     (0,   0,   128), "zebra":    (200, 200, 0  ),
}
PRIORITY = ["bear","elephant","person","cow","horse","dog","zebra","sheep","cat","bird"]

# ── Shared mutable state (all protected by locks) ─────────────────────────────
latest_jpeg    = None
frame_seq      = 0
frame_lock     = threading.Lock()

farm_latest_jpeg = None
farm_frame_seq = 0
farm_frame_bgr = None
farm_frame_lock = threading.Lock()
farm_camera_ok = False
farm_camera_error = "starting"

active_alerts  = []          # list of {name, conf, level, icon}

# Default to owner/farmer present. This keeps the security pipeline quiet unless
# the operator explicitly turns guard ON from the dashboard.
at_farm        = True
security_cam_on = True       # FLORA/admin can pause Security-camera detection
farm_cam_on     = True       # FLORA/admin can pause FarmMonitor scanning
at_farm_lock   = threading.Lock()

moisture_vals  = {p: None for p in PLANTS}
moisture_lock  = threading.Lock()

sensor_status  = {
    p: {"online": False, "value": None, "last_ok": None, "last_error": "not_read_yet", "fail_count": 0}
    for p in PLANTS
}
sensor_lock    = threading.Lock()

pump_states    = {p: False for p in PUMP_PLANTS}
pump_lock      = threading.Lock()
manual_pumps   = {p: False for p in PUMP_PLANTS}

auto_enabled   = True
auto_lock      = threading.Lock()

burst_state    = {p: "idle" for p in PUMP_PLANTS}
burst_timer    = {p: 0.0 for p in PUMP_PLANTS}
burst_ref      = {p: None for p in PUMP_PLANTS}   # moisture at soak start
cmd_deadline   = {p: 0.0 for p in PUMP_PLANTS}    # commanded-burst safety expiry (epoch s)

# History (for analytics)
moisture_hist  = {p: [] for p in PLANTS}  # {t, v}
detect_hist    = []    # {t, label, conf}
irr_hist       = []    # {t, plant}
_hist_lock     = threading.Lock()


# ── Dynamic sensor registration ─────────────────────────────────────────────
# Adds a moisture sensor (and optionally a relay) at runtime.
# Used by /api/sensors/add for the dashboard's `+ Add sensors` button.
def _register_extra_plant(letter: str, addr: int, channel: int,
                          relay_pin: int | None = None,
                          name: str | None = None) -> bool:
    letter = str(letter).strip().lower()
    if not letter or len(letter) != 1 or not letter.isalpha():
        return False
    # Mutate plant universe under the relevant locks so loops don't see a
    # half-registered plant.
    with sensor_lock:
        if letter not in PLANTS:
            PLANTS.append(letter)
            PLANTS.sort()
        SENSOR_CHANNELS[letter] = (int(addr), int(channel))
        sensor_status.setdefault(letter, {
            "online": False, "value": None, "last_ok": None,
            "last_error": "not_read_yet", "fail_count": 0,
        })
    with moisture_lock:
        moisture_vals.setdefault(letter, None)
    with _hist_lock:
        moisture_hist.setdefault(letter, [])
    _ads_errors.setdefault(letter, None)
    _ads_last_warn.setdefault(letter, 0.0)
    PLANT_NAMES.setdefault(letter, name or f"Plant {letter.upper()}")
    if name:
        PLANT_NAMES[letter] = name
    if relay_pin is not None:
        try:
            if GPIO_AVAILABLE and _gpio_handle is not None:
                GPIO.gpio_claim_output(_gpio_handle, int(relay_pin), RELAY_OFF_LEVEL)
            RELAY_PINS[letter] = int(relay_pin)
            if letter not in PUMP_PLANTS:
                PUMP_PLANTS.append(letter)
                PUMP_PLANTS.sort()
            with pump_lock:
                pump_states.setdefault(letter, False)
            manual_pumps.setdefault(letter, False)
            burst_state.setdefault(letter, "idle")
            burst_timer.setdefault(letter, 0.0)
            burst_ref.setdefault(letter, None)
            cmd_deadline.setdefault(letter, 0.0)
        except Exception as e:
            print(f"[WARN] could not claim relay pin {relay_pin} for plant {letter}: {e}")
    # Persist to .plants.json so the registration survives a restart.
    _PENDING_EXTRA_PLANTS[letter] = {
        "addr": int(addr), "channel": int(channel),
        **({"relay_pin": int(relay_pin)} if relay_pin is not None else {}),
    }
    if letter not in ACTIVE_PLANTS:
        ACTIVE_PLANTS.append(letter)
        ACTIVE_PLANTS.sort()
    _save_plant_registry()
    return True

# Re-apply persisted extras now that all the per-plant dicts exist.
for _p, _meta in dict(_PENDING_EXTRA_PLANTS).items():
    try:
        _register_extra_plant(
            _p, _meta.get("addr", ADS_ADDR), _meta.get("channel", 0),
            relay_pin=_meta.get("relay_pin"),
        )
    except Exception as _e:
        print(f"[WARN] could not restore plant {_p}: {_e}")


# Runtime notification email. Resets on restart so the dashboard asks again.
_notification_email = None
_notification_lock = threading.Lock()
_notify_last_sent = {}
_EMAIL_RE = re.compile(r'^[A-Za-z0-9._%+\-]+@[A-Za-z0-9.\-]+\.[A-Za-z]{2,}$')
ADMIN_ROLE = "admin"

farm_scan_lock = threading.Lock()
farm_scan_request = threading.Event()
farm_scan_status_lock = threading.Lock()
farm_scan_status = {
    "state": "idle",
    "message": "Waiting for scheduled scan",
    "next_scan_at": None,
    "last_scan_at": None,
    "last_result": None,
    "camera_ok": False,
    "camera_error": "starting",
    "stage": "idle",
    "total_cycles": FARM_MONITOR_SCAN_CYCLES,
    "current_cycle": 0,
    "target_frames": FARM_MONITOR_BATCH_FRAMES,
    "captured_frames": 0,
    "usable_frames": 0,
    "skipped_frames": 0,
    "fallback_quality_frames": 0,
    "analyzing_model": "",
    "disease_frames": 0,
    "ripeness_frames": 0,
    "disease_ratio": 0,
    "ripeness_ratio": 0,
    "model_names": {
        "disease": "Plant Health model",
        "ripeness": "Harvest Readiness model",
    },
}

def _read_demo_mail_config():
    cfg = {"smtp": {}, "notifications": {}}
    path = Path(__file__).parent / "config_demo.yaml"
    if not path.exists():
        return cfg
    section = None
    try:
        for raw in path.read_text(encoding="utf-8").splitlines():
            line = raw.strip()
            if not line or line.startswith('#'):
                continue
            if not raw.startswith(' ') and line.endswith(':'):
                section = line[:-1]
                cfg.setdefault(section, {})
                continue
            if section and ':' in line:
                key, value = line.split(':', 1)
                cfg.setdefault(section, {})[key.strip()] = value.strip().strip('"\'')
    except Exception as e:
        print(f"[WARN] config_demo.yaml read failed: {e}")
    return cfg

_MAIL_CFG = _read_demo_mail_config()

def _smtp_ready():
    cfg = _read_demo_mail_config()
    smtp = cfg.get('smtp', {})
    password = smtp.get('password', '')
    required = [smtp.get('host'), smtp.get('port'), smtp.get('email'), password]
    return all(required) and set(password.lower()) != {'x'}

def _send_email_now(to_email: str, subject: str, body: str):
    if not _smtp_ready():
        print('[EMAIL] SMTP config not ready; notification stored in runtime only')
        return
    smtp = _MAIL_CFG.get('smtp', {})
    msg = EmailMessage()
    msg['Subject'] = subject
    msg['From'] = smtp.get('from_email') or smtp.get('email')
    msg['To'] = to_email
    msg.set_content(body)
    try:
        with smtplib.SMTP(smtp.get('host'), int(smtp.get('port', 587)), timeout=12) as server:
            server.starttls()
            server.login(smtp.get('email'), smtp.get('password'))
            server.send_message(msg)
        print(f'[EMAIL] notification sent to {to_email}')
    except Exception as e:
        print(f'[WARN] email notification failed: {e}')

def _send_email_html_now(to_email: str, subject: str, text_body: str, html_body: str, attachments=None):
    if not _smtp_ready():
        print('[EMAIL] SMTP config not ready; farm monitor notification skipped')
        return
    smtp = _MAIL_CFG.get('smtp', {})
    msg = EmailMessage()
    msg['Subject'] = subject
    msg['From'] = smtp.get('from_email') or smtp.get('email')
    msg['To'] = to_email
    msg.set_content(text_body)
    msg.add_alternative(html_body, subtype="html")
    for path in attachments or []:
        try:
            p = Path(path)
            if not p.exists() or not p.is_file():
                continue
            subtype = "jpeg" if p.suffix.lower() in (".jpg", ".jpeg") else "png"
            msg.add_attachment(p.read_bytes(), maintype="image", subtype=subtype, filename=p.name)
        except Exception as e:
            print(f"[WARN] email attachment skipped: {e}")
    try:
        with smtplib.SMTP(smtp.get('host'), int(smtp.get('port', 587)), timeout=18) as server:
            server.starttls()
            server.login(smtp.get('email'), smtp.get('password'))
            server.send_message(msg)
        print(f'[EMAIL] farm monitor notification sent to {to_email}')
    except Exception as e:
        print(f'[WARN] farm monitor email failed: {e}')

def _queue_notification_email(subject: str, body: str, key: str = 'general', min_gap: float = 60.0):
    with _notification_lock:
        to_email = _notification_email
        if not to_email:
            return
        now = time.time()
        if now - _notify_last_sent.get(key, 0) < min_gap:
            return
        _notify_last_sent[key] = now
    threading.Thread(target=_send_email_now, args=(to_email, subject, body), daemon=True).start()


def _queue_notification_email_html(subject: str, text_body: str, html_body: str,
                                   key: str = 'general-html', min_gap: float = 60.0):
    with _notification_lock:
        to_email = _notification_email
        if not to_email:
            return
        now = time.time()
        if now - _notify_last_sent.get(key, 0) < min_gap:
            return
        _notify_last_sent[key] = now
    threading.Thread(
        target=_send_email_html_now,
        args=(to_email, subject, text_body, html_body, []),
        daemon=True,
    ).start()


def _queue_direct_email_html(to_email: str, subject: str, text_body: str, html_body: str,
                             key: str = 'direct-html', min_gap: float = 1.0):
    """Send a one-off HTML email without changing the farm alert recipient."""
    with _notification_lock:
        now = time.time()
        bucket = f"{key}:{to_email}"
        if now - _notify_last_sent.get(bucket, 0) < min_gap:
            return False
        _notify_last_sent[bucket] = now
    threading.Thread(
        target=_send_email_html_now,
        args=(to_email, subject, text_body, html_body, []),
        daemon=True,
    ).start()
    return True


def _subscription_email_html(to_email: str) -> tuple[str, str, str]:
    dashboard_url = _MAIL_CFG.get('app', {}).get('dashboard_url', 'https://aigriculture.in')
    safe_email = html_lib.escape(to_email)
    safe_url = html_lib.escape(dashboard_url)
    subject = "Welcome to AIgriculture Admin"
    text = (
        "Welcome to AIgriculture Admin.\n"
        "Thank you for subscribing to AIgriculture farm emails. "
        "Important updates from your farm will be sent here.\n"
        f"Dashboard: {dashboard_url}\n"
    )
    html = f"""<!doctype html>
<html>
  <head>
    <meta name="viewport" content="width=device-width,initial-scale=1">
    <style>
      @media only screen and (max-width:620px){{
        .wrap{{padding:14px 10px!important}}
        .card{{border-radius:22px!important}}
        .hero{{padding:26px 20px!important}}
        .body{{padding:24px 20px!important}}
        .title{{font-size:27px!important}}
        .msg{{font-size:15px!important}}
        .btn{{display:block!important;text-align:center!important}}
      }}
    </style>
  </head>
  <body style="margin:0;background:#eefbf8;font-family:Arial,Helvetica,sans-serif;color:#12312c;-webkit-text-size-adjust:100%;text-size-adjust:100%">
    <div style="display:none;max-height:0;overflow:hidden">Your AIgriculture farm email alerts are now active.</div>
    <div class="wrap" style="max-width:600px;margin:0 auto;padding:20px 12px;background:#eefbf8">
      <div class="card" style="background:#ffffff;border:1px solid #cde9e3;border-radius:26px;overflow:hidden;box-shadow:0 14px 34px rgba(13,138,120,.12)">
        <div class="hero" style="padding:34px 32px;background:linear-gradient(135deg,#e7fff7,#ffffff);border-bottom:1px solid #d6eee8">
          <div style="display:inline-block;background:#dffaf3;color:#0d8a78;border:1px solid #bde8de;border-radius:999px;padding:8px 13px;font-size:12px;font-weight:900;letter-spacing:.7px;text-transform:uppercase">Subscription active</div>
          <div class="title" style="font-size:32px;line-height:1.12;font-weight:900;color:#12312c;margin-top:18px">Welcome to AIgriculture Admin</div>
          <div style="font-size:15px;line-height:1.5;color:#5d7b74;margin-top:10px">Strawberry Monitoring Console</div>
        </div>
        <div class="body" style="padding:30px 32px;background:#ffffff">
          <p class="msg" style="font-size:16px;line-height:1.65;color:#29423c;margin:0 0 16px">Thank you for subscribing to AIgriculture emails. We will send important farm updates, security alerts, harvest readiness messages, and plant health warnings to this address.</p>
          <div style="border:1px solid #d8eee8;background:#f6fffc;border-radius:18px;padding:16px;margin:20px 0">
            <div style="font-size:12px;text-transform:uppercase;letter-spacing:1px;color:#6b8a83;font-weight:800">Subscribed email</div>
            <div style="font-size:15px;line-height:1.45;color:#12312c;font-weight:800;margin-top:6px;word-break:break-word">{safe_email}</div>
          </div>
          <a class="btn" href="{safe_url}" style="display:inline-block;background:linear-gradient(180deg,#1cc7a5,#0d8a78);color:#ffffff;text-decoration:none;font-weight:900;font-size:15px;border-radius:16px;padding:14px 20px">Open dashboard</a>
        </div>
        <div style="padding:15px 32px;background:#f4fbfa;border-top:1px solid #d6eee8;color:#66827c;font-size:12px;line-height:1.55">
          You can change the notification email from dashboard settings while the farm console is running.
        </div>
      </div>
    </div>
  </body>
</html>"""
    return subject, text, html




def _queue_designer_email(kind: str, *, title: str = "", message: str = "", label: str = "",
                          disease_ratio: float = 0.0, ripeness_ratio: float = 0.0,
                          images=None, rows=None):
    """Send farmer-facing HTML email through the standalone designer script."""
    script = BASE_DIR / "farm_monitor_designer_email.py"
    if not script.exists():
        print("[WARN] designer email script missing; email skipped")
        return
    cmd = [
        sys.executable, str(script),
        "--event-type", kind,
        "--title", title,
        "--message", message,
        "--detection-label", label,
        "--disease-ratio", str(disease_ratio),
        "--ripeness-ratio", str(ripeness_ratio),
    ]
    with _notification_lock:
        to_email = _notification_email
    if to_email:
        cmd.extend(["--to", to_email])
    for row in rows or []:
        cmd.extend(["--row", row])
    for img in images or []:
        if img:
            cmd.extend(["--image", str(img)])

    def _run():
        try:
            proc = subprocess.run(cmd, cwd=str(BASE_DIR), text=True, capture_output=True, timeout=45)
            if proc.returncode == 0:
                print("[EMAIL] designer notification sent")
            else:
                print(f"[WARN] designer notification failed: {proc.stderr.strip() or proc.stdout.strip()}")
        except Exception as e:
            print(f"[WARN] designer notification failed: {e}")

    threading.Thread(target=_run, daemon=True).start()

# WebSocket clients
_ws_clients: list = []
_ws_lock = threading.Lock()

# ── ADS1115 helpers ────────────────────────────────────────────────────────────
_ads_errors = {p: None for p in PLANTS}
_ads_last_warn = {p: 0.0 for p in PLANTS}

def _read_ads_channel(plant: str, addr: int, ch: int):
    """Return moisture % for one ADS1115 channel, or None on error."""
    if not I2C_AVAILABLE:
        _ads_errors[plant] = "i2c_unavailable"
        return None
    try:
        cfg = MUX_CONFIGS[ch]
        _bus.write_i2c_block_data(addr, REG_CFG, [(cfg >> 8) & 0xFF, cfg & 0xFF])
        time.sleep(ADS_WAIT_S)
        data = _bus.read_i2c_block_data(addr, REG_CONV, 2)
        raw  = struct.unpack(">h", bytes(data))[0]
        if raw <= -32768 or raw >= 32767:
            _ads_errors[plant] = f"invalid_raw:{raw}"
            return None
        pct = (DRY_VALUE - raw) / (DRY_VALUE - WET_VALUE) * 100.0
        _ads_errors[plant] = None
        return round(max(0.0, min(100.0, pct)), 1)
    except Exception as e:
        _ads_errors[plant] = str(e)
        now = time.time()
        if now - _ads_last_warn[plant] >= ADS_WARN_S:
            _ads_last_warn[plant] = now
            print(f"[WARN] ADS1115 plant {plant.upper()} addr 0x{addr:02x} ch{ch}: {e}")
        return None

def _update_sensor_status(plant: str, value, error: str | None):
    now = time.time()
    with sensor_lock:
        st = sensor_status[plant]
        if value is None:
            st["online"] = False
            st["value"] = None
            st["last_error"] = error or "read_failed"
            st["fail_count"] = int(st.get("fail_count", 0)) + 1
        else:
            st["online"] = True
            st["value"] = value
            st["last_ok"] = now
            st["last_error"] = None
            st["fail_count"] = 0
    with moisture_lock:
        moisture_vals[plant] = value

def _sensor_snapshot():
    with sensor_lock:
        return {p: dict(sensor_status[p]) for p in PLANTS}

# ── GPIO relay helpers ─────────────────────────────────────────────────────────
def set_relay(plant: str, on: bool):
    """Energise (on=True) or release (on=False) the relay for a plant.
    Sensor-only plants (added via `+ Add sensors`) have no relay pin — no-op."""
    if not GPIO_AVAILABLE:
        return
    pin = RELAY_PINS.get(plant)
    if pin is None:
        return
    GPIO.gpio_write(_gpio_handle, pin, RELAY_ON_LEVEL if on else RELAY_OFF_LEVEL)

def all_relays_off():
    for p in PUMP_PLANTS:
        set_relay(p, False)

def _stop_plant_pump(plant: str):
    set_relay(plant, False)
    with pump_lock:
        pump_states[plant] = False
    manual_pumps[plant] = False
    burst_state[plant] = "idle"
    cmd_deadline[plant] = 0.0

def _drive_burst(plant: str, mv, now: float):
    """Advance the 3s-ON / 10s-soak burst cycle for one plant.

    mv may be None (sensor offline) for a commanded blind burst — the fixed
    cadence still bounds water delivery, and the caller enforces the CMD_MAX_S
    time-box plus the STOP_PCT / LOCK_PCT cut-offs.
    """
    state = burst_state[plant]
    if state == "idle":
        burst_state[plant] = "burst_on"
        burst_timer[plant] = now + BURST_ON_S
        set_relay(plant, True)
        with pump_lock:
            pump_states[plant] = True
        with _hist_lock:
            irr_hist.append({"t": now, "plant": plant})
    elif state == "burst_on":
        if now >= burst_timer[plant]:
            burst_state[plant] = "burst_wait"
            burst_timer[plant] = now + BURST_WAIT_S
            burst_ref[plant] = mv
            set_relay(plant, False)
            with pump_lock:
                pump_states[plant] = False
    elif state == "burst_wait":
        if now >= burst_timer[plant]:
            ref = burst_ref[plant]
            if mv is not None and ref is not None and mv - ref >= BURST_CLIMB_SKIP:
                # Soil still drinking — moisture rising on its own; skip a burst.
                burst_timer[plant] = now + BURST_WAIT_S
                burst_ref[plant] = mv
            else:
                burst_state[plant] = "burst_on"
                burst_timer[plant] = now + BURST_ON_S
                set_relay(plant, True)
                with pump_lock:
                    pump_states[plant] = True
                with _hist_lock:
                    irr_hist.append({"t": now, "plant": plant})

# ── Sensor + auto-irrigation loop ─────────────────────────────────────────────
def sensor_irr_loop():
    """Reads ADS1115 quickly and runs the burst auto-irrigation state machine."""
    while True:
      try:
        now = time.time()

        # 1. Read real sensors only. Failed channels become offline/null.
        # Snapshot because /api/sensors/add can extend SENSOR_CHANNELS live.
        for plant, (addr, ch) in list(SENSOR_CHANNELS.items()):
            val = _read_ads_channel(plant, addr, ch)
            _update_sensor_status(plant, val, _ads_errors.get(plant))

            # Append to history (downsample: keep 1 per ~10s → ~8640/day)
            if val is not None:
                with _hist_lock:
                    h = moisture_hist[plant]
                    if not h or now - h[-1]["t"] >= 10:
                        h.append({"t": now, "v": val})
                        if len(h) > 8640:
                            h.pop(0)

        # 2. Auto-irrigation state machine
        with auto_lock:
            auto_on = auto_enabled

        for plant in PUMP_PLANTS:
            with moisture_lock:
                mv = moisture_vals[plant]
            commanded = manual_pumps[plant]      # operator / FLORA requested a burst
            state = burst_state[plant]

            # Any commanded session is time-boxed so a blind (sensor-offline)
            # burst can never run forever — lazy-init the deadline so it holds
            # no matter who set manual_pumps (dashboard button or FLORA).
            if commanded and not cmd_deadline[plant]:
                cmd_deadline[plant] = now + CMD_MAX_S
            if commanded and now >= cmd_deadline[plant]:
                _stop_plant_pump(plant)
                print(f"[CMD] Plant {plant.upper()} commanded burst expired (max {CMD_MAX_S:.0f}s)")
                continue

            # ── Sensor offline ───────────────────────────────────────────────
            if mv is None:
                # Auto bursts cannot run blind; stop them. A commanded burst is
                # allowed to continue blind (time-boxed above) so the admin can
                # still water when a sensor is unplugged.
                if not commanded:
                    if state != "idle":
                        _stop_plant_pump(plant)
                        print(f"[SENSOR] Plant {plant.upper()} offline — auto burst stopped")
                    continue
                starting = state == "idle"
                _drive_burst(plant, None, now)
                if starting and burst_state[plant] == "burst_on":
                    print(f"[CMD] Plant {plant.upper()} blind burst start (sensor offline)")
                continue

            # ── HARD-STOP SAFETY NET (real reading) ──────────────────────────
            # Absolute lock: no pump — auto or commanded — runs at/above LOCK_PCT.
            if mv >= LOCK_PCT and (state != "idle" or commanded):
                _stop_plant_pump(plant)
                print(f"[HARDLOCK] Plant {plant.upper()} forced OFF — {mv:.1f}% ≥ {LOCK_PCT}%")
                continue

            # Target reached: stop and clear the session (auto or commanded).
            if mv >= STOP_PCT and (state != "idle" or commanded):
                _stop_plant_pump(plant)
                print(f"[STOP] Plant {plant.upper()} target reached — {mv:.1f}% ≥ {STOP_PCT}%")
                continue
            # ─────────────────────────────────────────────────────────────────

            # A burst session is active when explicitly commanded, or when AUTO
            # is on (start below TRIGGER, then continue the cycle until STOP).
            # Both paths drive the identical 3s-ON / 10s-soak machine.
            want_session = commanded or (auto_on and (state != "idle" or mv < TRIGGER_PCT))
            if not want_session:
                if state != "idle":
                    _stop_plant_pump(plant)
                continue

            starting = state == "idle"
            _drive_burst(plant, mv, now)
            if starting and burst_state[plant] == "burst_on":
                tag = "CMD" if commanded else "AUTO"
                print(f"[{tag}] Plant {plant.upper()} burst start ({mv:.1f}%)")

        time.sleep(max(0.1, SENSOR_POLL_S))
      except Exception as _e:
        print(f"[CRITICAL] sensor_irr_loop crashed: {_e}", flush=True)
        try:
            all_relays_off()
        except Exception:
            pass
        time.sleep(5.0)

# ── WebSocket broadcast (async) ────────────────────────────────────────────────
async def broadcast(data: dict):
    msg  = json.dumps(data)
    dead = []
    with _ws_lock:
        clients = list(_ws_clients)
    for ws in clients:
        try:
            await ws.send_text(msg)
        except Exception as _e:
            hailo_logger.debug(f"WS send error ({type(_e).__name__}): {_e}")
            dead.append(ws)
    if dead:
        with _ws_lock:
            for d in dead:
                if d in _ws_clients:
                    _ws_clients.remove(d)

def _last_watered_map() -> dict:
    """Most recent irrigation timestamp (epoch s) per plant, from irr_hist."""
    lw = {}
    with _hist_lock:
        for e in irr_hist:
            lw[e["plant"]] = e["t"]
    return lw

async def ws_push_task():
    """Push live state to all WebSocket clients every 1 second."""
    while True:
        try:
            with moisture_lock:
                mv = dict(moisture_vals)
            with pump_lock:
                ps = dict(pump_states)
            with at_farm_lock:
                af = at_farm
            with auto_lock:
                ae = auto_enabled
            ss = _sensor_snapshot()

            payload = {
                "type":     "state",
                "active_plants": ACTIVE_PLANTS,
                "all_plants":    list(PLANTS),
                "plant_names": PLANT_NAMES,
                "moisture": mv,
                "sensor_status": ss,
                "pumps":    ps,
                "auto_irr": ae,
                "at_farm":  af,
                "alerts":   active_alerts,
                "burst":    dict(burst_state),
                "last_watered": _last_watered_map(),
                "farm_monitor": _farm_status_snapshot(),
            }
            await broadcast(payload)
        except asyncio.CancelledError:
            break
        except Exception as e:
            print(f"[WS] push error: {e}")
        await asyncio.sleep(1.0)   # ← push every 1 second

# ── CPU YOLO security camera ───────────────────────────────────────────────────
# Same logic the Hailo callback runs, just driven by Ultralytics on the CPU.
# Frame-skip + a class allow-list keep load low even on a Pi 4. Updates the
# same shared state (active_alerts, latest_jpeg, detect_hist) that the
# dashboard, /api routes, and FLORA tools all read from — so the UX is
# identical to the Hailo build.

class _Picamera2VideoCapture:
    """cv2.VideoCapture-compatible wrapper around picamera2 for CSI cameras.

    On modern Raspberry Pi OS (Bookworm+) the CSI camera is owned by libcamera
    and can't be opened via V4L2 / OpenCV directly — opening /dev/video0 looks
    successful but `cap.read()` returns no frames. picamera2 is the correct
    path. This adapter lets the rest of the pipeline keep its `cap.read()` /
    `cap.isOpened()` / `cap.release()` interface unchanged.
    """
    def __init__(self, width: int = 1280, height: int = 720, cam_index: int = 0):
        if not _PICAMERA2_AVAILABLE or _Picamera2 is None:
            raise RuntimeError("picamera2 not installed")
        try:
            self._cam = _Picamera2(cam_index)
        except TypeError:
            # Older picamera2 versions don't accept a positional camera index.
            self._cam = _Picamera2()
        cfg = self._cam.create_preview_configuration(
            main={"size": (int(width), int(height)), "format": "RGB888"}
        )
        self._cam.configure(cfg)
        self._cam.start()
        self._opened = True

    def isOpened(self) -> bool:
        return bool(self._opened)

    def read(self):
        if not self._opened or cv2 is None:
            return False, None
        try:
            arr = self._cam.capture_array()
            return True, cv2.cvtColor(arr, cv2.COLOR_RGB2BGR)
        except Exception:
            return False, None

    def release(self):
        try:
            if self._opened:
                self._cam.stop()
        except Exception:
            pass
        self._opened = False

    def set(self, *_a, **_kw):  # most CAP_PROP_* don't apply — no-op
        return False

    def get(self, *_a, **_kw):
        return 0.0


def _open_video_source(source: str):
    """Return an open VideoCapture (or picamera2 adapter) for CSI / USB / RTSP / HTTP / index inputs."""
    if cv2 is None:
        return None
    src = (source or "").strip()
    if not src:
        return None
    if src.lower().startswith("rtsp"):
        os.environ.setdefault("OPENCV_FFMPEG_CAPTURE_OPTIONS", "rtsp_transport;tcp")
        return cv2.VideoCapture(src, cv2.CAP_FFMPEG)
    if src.startswith("/dev/"):
        return cv2.VideoCapture(src, cv2.CAP_V4L2)
    if src.lower() in ("rpi", "csi", "csi:0", "csi:1"):
        # CSI cameras on Bookworm+ are owned by libcamera — V4L2 capture silently
        # returns empty frames. Prefer picamera2 when installed.
        cam_index = 1 if src.lower() == "csi:1" else 0
        if _PICAMERA2_AVAILABLE:
            try:
                return _Picamera2VideoCapture(cam_index=cam_index)
            except Exception as e:
                hailo_logger.warning(
                    f"picamera2 init failed ({e}); falling back to V4L2 /dev/video{cam_index}"
                )
        return cv2.VideoCapture(f"/dev/video{cam_index}", cv2.CAP_V4L2)
    try:
        return cv2.VideoCapture(int(src))
    except ValueError:
        return cv2.VideoCapture(src)


def cpu_security_camera_loop(source: str):
    """Capture → infer (frame-skip) → trigger siren + save snapshot + publish
    MJPEG. Runs in its own thread. Same shared state as the Hailo callback."""
    global latest_jpeg, frame_seq, active_alerts

    if not source or cv2 is None:
        hailo_logger.info("Security camera disabled (no source / OpenCV missing)")
        return

    try:
        from ultralytics import YOLO
    except Exception as e:
        hailo_logger.error(f"ultralytics not installed ({e}) — security camera disabled")
        return

    # Default to YOLOv8s ("small") rather than nano — meaningfully better recall on
    # the farm-threat classes (person / bear / elephant / cow / dog / horse / ...)
    # at ~3× the per-frame cost. On a Pi 5 with the default SECURITY_FRAME_SKIP=5
    # this is still well under one inference per second of wall clock. Operators
    # who want max FPS can set SECURITY_MODEL=yolov8n.pt in .env to revert.
    # Prefer Models/yolov8s.pt if present; otherwise pass the bare name so
    # Ultralytics auto-downloads the weights into the working directory.
    _default_security = "yolov8s.pt"
    _models_dir_candidate = BASE_DIR / "Models" / _default_security
    if _models_dir_candidate.exists():
        _default_security = str(_models_dir_candidate)
    model_path = os.getenv("SECURITY_MODEL", _default_security)
    try:
        model = YOLO(model_path)
    except Exception as e:
        hailo_logger.error(f"Failed to load YOLO model {model_path!r}: {e}")
        return

    # Pre-resolve COCO class indices so we only run inference on the labels we
    # care about — same allow-list the Hailo build uses (FARM_THREATS).
    try:
        name_to_idx = {v: int(k) for k, v in model.names.items()}
    except Exception:
        name_to_idx = {}
    allow_class_ids = sorted({name_to_idx[n] for n in FARM_THREATS if n in name_to_idx})
    hailo_logger.info(
        f"CPU security camera ready: src={source} model={model_path} "
        f"classes={[n for n in FARM_THREATS if n in name_to_idx]}"
    )

    cap = _open_video_source(source)
    if cap is None or not cap.isOpened():
        hailo_logger.error(f"Could not open security camera at {source!r}")
        return

    FRAME_SKIP   = max(1, int(os.getenv("SECURITY_FRAME_SKIP", "5")))
    # 640 is the size YOLOv8 was trained at — better recall on small / distant
    # subjects (a person at 30 px is below the noise floor at 480). Drop to 480
    # if you need more CPU headroom.
    INFER_IMGSZ  = max(160, int(os.getenv("SECURITY_IMGSZ", "640")))
    min_jpeg_dt  = max(0.03, 1.0 / max(1.0, STREAM_TARGET_FPS))
    last_jpeg_ts = 0.0
    last_save: dict = {}
    frame_idx = 0
    last_boxes: list = []   # carry-over boxes between inferred frames so the
                            # stream doesn't flicker on skipped frames

    while True:
        ret, frame_bgr = cap.read()
        if not ret or frame_bgr is None:
            time.sleep(0.5)
            continue

        frame_idx += 1
        now = time.time()

        with at_farm_lock:
            guard_on = not at_farm

        # ── Guard OFF / camera paused ────────────────────────────────────────
        if not guard_on or not security_cam_on:
            if active_alerts:
                active_alerts = []
            _set_siren(False)
            last_boxes = []
            if now - last_jpeg_ts >= min_jpeg_dt:
                last_jpeg_ts = now
                fh, fw = frame_bgr.shape[:2]
                cv2.rectangle(frame_bgr, (0, fh - 36), (fw, fh), (0, 60, 0), -1)
                cv2.putText(frame_bgr, "GUARD OFF  |  Owner is at the farm",
                            (10, fh - 10), cv2.FONT_HERSHEY_SIMPLEX, 0.6,
                            (100, 255, 100), 2)
                _, jpeg = cv2.imencode(".jpg", frame_bgr,
                                       [cv2.IMWRITE_JPEG_QUALITY, STREAM_JPEG_QUALITY])
                with frame_lock:
                    latest_jpeg = jpeg.tobytes()
                    frame_seq += 1
            continue

        # ── Inference (only every Nth frame) ─────────────────────────────────
        threats: list = []
        confs:   dict = {}
        boxes:   list = []
        ran_inference = False

        if frame_idx % FRAME_SKIP == 0 and allow_class_ids:
            ran_inference = True
            try:
                results = model.predict(
                    frame_bgr,
                    classes=allow_class_ids,
                    conf=CONF_THRESH,
                    imgsz=INFER_IMGSZ,
                    verbose=False,
                )
            except Exception as e:
                hailo_logger.warning(f"YOLO predict failed: {e}")
                results = []
            for r in results:
                if r.boxes is None:
                    continue
                for box in r.boxes:
                    cls = int(box.cls[0])
                    conf = float(box.conf[0])
                    label = model.names.get(cls, "")
                    if label not in FARM_THREATS or conf < CONF_THRESH:
                        continue
                    x1, y1, x2, y2 = [int(v) for v in box.xyxy[0]]
                    threats.append(label)
                    confs[label] = round(conf * 100)
                    boxes.append((label, conf, (x1, y1, x2, y2)))
            last_boxes = boxes
        else:
            # Use last detection on skipped frames so MJPEG stream stays in sync
            for label, conf, xyxy in last_boxes:
                threats.append(label)
                confs[label] = max(confs.get(label, 0), round(conf * 100))
                boxes.append((label, conf, xyxy))

        active_alerts = [
            {"name":  lbl,
             "conf":  confs.get(lbl, 0),
             "level": THREAT_LEVEL.get(lbl, "low"),
             "icon":  THREAT_EMOJI.get(lbl, "🐾")}
            for lbl in set(threats)
        ]
        _set_siren(bool(threats))

        # Draw boxes
        for label, conf, (x1, y1, x2, y2) in boxes:
            col = COLORS.get(label, (0, 255, 0))
            cv2.rectangle(frame_bgr, (x1, y1), (x2, y2), col, 3)
            txt = f"{label} {conf:.2f}"
            (tw, th), _ = cv2.getTextSize(txt, cv2.FONT_HERSHEY_SIMPLEX, 0.7, 2)
            cv2.rectangle(frame_bgr, (x1, y1 - th - 10), (x1 + tw + 6, y1), col, -1)
            cv2.putText(frame_bgr, txt, (x1 + 3, y1 - 5),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 0, 0), 2)

        # Detection history + event snapshot (rate-limited per label)
        if ran_inference:
            for lbl in set(threats):
                with _hist_lock:
                    detect_hist.append({"t": now, "label": lbl, "conf": confs.get(lbl, 0)})
                    if len(detect_hist) > 10000:
                        detect_hist.pop(0)
                if now - last_save.get(lbl, 0) > 30:
                    last_save[lbl] = now
                    _save_event(lbl, frame_bgr.copy(), confs.get(lbl, 0) / 100.0)

        # MJPEG publish
        if now - last_jpeg_ts >= min_jpeg_dt:
            last_jpeg_ts = now
            fh, fw = frame_bgr.shape[:2]
            if threats:
                unique = list(set(threats))
                cv2.rectangle(frame_bgr, (0, 0), (fw, 50), (0, 0, 180), -1)
                cv2.putText(frame_bgr, f"ALERT: {', '.join(unique).upper()}",
                            (10, 36), cv2.FONT_HERSHEY_SIMPLEX, 1.0, (255, 255, 255), 2)
            else:
                cv2.rectangle(frame_bgr, (0, fh - 32), (fw, fh), (0, 70, 0), -1)
                cv2.putText(frame_bgr, "Farm Guardian | Clear",
                            (10, fh - 8), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (180, 255, 180), 1)
            _, jpeg = cv2.imencode(".jpg", frame_bgr,
                                   [cv2.IMWRITE_JPEG_QUALITY, STREAM_JPEG_QUALITY])
            with frame_lock:
                latest_jpeg = jpeg.tobytes()
                frame_seq += 1

# ── Storage helpers ────────────────────────────────────────────────────────────
def _security_display_label(label: str) -> str:
    """Return a clean user-facing object name for security camera events."""
    clean = re.sub(r"[_-]+", " ", str(label or "").strip()).strip()
    return clean.title() if clean else "Farm Activity"

def _security_event_message(label: str) -> str:
    display = _security_display_label(label)
    lower = display.lower()
    if lower == "person":
        return "A person was seen near the farm area."
    article = "An" if lower[:1] in "aeiou" else "A"
    return f"{article} {lower} was detected near the farm area."

def _save_event(label: str, frame_bgr=None, conf: float = 0.0):
    try:
        with at_farm_lock:
            if at_farm:
                return
        ts     = datetime.now()
        folder = (STORAGE_PATH / ts.strftime("%Y") / ts.strftime("%m")
                  / ts.strftime("%d") / ts.strftime("%H-%M-%S"))
        folder.mkdir(parents=True, exist_ok=True)
        display_label = _security_display_label(label)
        security_message = _security_event_message(label)
        meta = {
            "label": f"Security Camera: {label}",
            "conf": round(conf, 3),
            "time": ts.isoformat(),
            "event_type": "security",
            "message": security_message,
        }
        saved_images = []
        attachments = []
        if frame_bgr is not None:
            tmp_img = folder / "event.tmp.jpg"
            cv2.imwrite(str(tmp_img), frame_bgr)
            hashed_img = folder / _opaque_hashed_filename(tmp_img)
            tmp_img.replace(hashed_img)
            saved_images.append(_public_storage_name(hashed_img))
            attachments.append(hashed_img)
        if saved_images:
            meta["images"] = saved_images
        (folder / "meta.json").write_text(json.dumps(meta, indent=2), encoding="utf-8")
        _queue_designer_email(
            "security",
            title="Farm security activity detected",
            message=security_message,
            label=display_label,
            images=attachments,
            rows=[
                f"{display_label}|Seen|Check camera",
                "Farm area|Needs review|Open dashboard",
            ],
        )
    except Exception as e:
        print(f"[WARN] save_event: {e}")

def _get_storage_tree():
    if not STORAGE_PATH.exists():
        return {}
    tree = {}
    try:
        for yr in sorted(STORAGE_PATH.iterdir()):
            if not yr.is_dir(): continue
            tree[yr.name] = {}
            for mo in sorted(yr.iterdir()):
                if not mo.is_dir(): continue
                tree[yr.name][mo.name] = {}
                for day in sorted(mo.iterdir()):
                    if not day.is_dir(): continue
                    events = []
                    for evt in sorted(day.iterdir()):
                        if not evt.is_dir(): continue
                        mf   = evt / "meta.json"
                        meta = {}
                        if mf.exists():
                            try: meta = json.loads(mf.read_text())
                            except: pass
                        imgs = sorted(_public_storage_name(f) for f in evt.iterdir() if f.suffix.lower() in (".jpg", ".jpeg", ".png"))
                        events.append({"time": evt.name, "meta": meta, "images": imgs})
                    tree[yr.name][mo.name][day.name] = events
    except Exception as e:
        print(f"[WARN] storage tree: {e}")
    return tree


# ── MJPEG stream generator ─────────────────────────────────────────────────────
def _gen_frames():
    last_seq = -1
    idle_sleep = max(0.02, 1.0 / max(1.0, STREAM_TARGET_FPS * 2.0))
    while True:
        with frame_lock:
            frame = latest_jpeg
            seq = frame_seq
        if frame and seq != last_seq:
            last_seq = seq
            yield (b"--frame\r\nContent-Type: image/jpeg\r\n\r\n"
                   + frame + b"\r\n")
        else:
            time.sleep(idle_sleep)


# ── Farm Monitor stream and scan workflow ─────────────────────────────────────
def _farm_status_update(**updates):
    with farm_scan_status_lock:
        farm_scan_status.update(updates)


def _farm_status_snapshot():
    with farm_scan_status_lock:
        snap = dict(farm_scan_status)
    with farm_frame_lock:
        snap["camera_ok"] = farm_camera_ok
        snap["camera_error"] = farm_camera_error
        snap["frame_seq"] = farm_frame_seq
    return snap


def farm_monitor_camera_loop():
    """Own the USB Farm Monitor camera for preview and scheduled batch capture."""
    global farm_latest_jpeg, farm_frame_seq, farm_frame_bgr, farm_camera_ok, farm_camera_error, FARM_MONITOR_CAMERA
    if cv2 is None:
        farm_camera_error = "OpenCV unavailable"
        return
    if not FARM_MONITOR_CAMERA and not USE_RPICAM:
        farm_camera_ok = False
        farm_camera_error = "No USB Farm Monitor camera detected"
        while not FARM_MONITOR_CAMERA:
            # USB cameras can appear after the dashboard starts. Keep probing so
            # FarmMonitor recovers without requiring a server restart.
            FARM_MONITOR_CAMERA = _auto_detect_usb_camera(os.getenv("FARM_MONITOR_CAMERA", ""))
            if FARM_MONITOR_CAMERA:
                farm_camera_error = f"Opening FarmMonitor camera {FARM_MONITOR_CAMERA}"
                break
            time.sleep(2.0)
    interval = max(0.05, 1.0 / max(1.0, FARM_MONITOR_FPS))
    cap = None
    while True:
        try:
            if USE_RPICAM and _PICAMERA2_AVAILABLE:
                # ── picamera2 capture branch ───────────────────────────────
                _cam = _Picamera2()
                _cfg = _cam.create_preview_configuration(
                    main={"size": (FARM_MONITOR_WIDTH, FARM_MONITOR_HEIGHT), "format": "RGB888"}
                )
                _cam.configure(_cfg)
                _cam.start()
                try:
                    while True:
                        _frame_rgb = _cam.capture_array()
                        frame_bgr = __import__("cv2").cvtColor(_frame_rgb, __import__("cv2").COLOR_RGB2BGR)
                        farm_camera_ok = True
                        farm_camera_error = ""
                        _, jpeg = __import__("cv2").imencode(".jpg", frame_bgr,
                                   [__import__("cv2").IMWRITE_JPEG_QUALITY, FARM_MONITOR_JPEG_QUALITY])
                        with farm_frame_lock:
                            farm_frame_bgr = frame_bgr.copy()
                            farm_latest_jpeg = jpeg.tobytes()
                            farm_frame_seq += 1
                        __import__("time").sleep(max(0.05, 1.0 / max(1.0, FARM_MONITOR_FPS)))
                finally:
                    _cam.stop()
                return  # picamera2 loop handles everything; skip OpenCV loop
            # ── OpenCV / V4L2 fallback (original code) ────────────────────
            if cap is None or not cap.isOpened():
                if not FARM_MONITOR_CAMERA:
                    FARM_MONITOR_CAMERA = _auto_detect_usb_camera(os.getenv("FARM_MONITOR_CAMERA", ""))
                    if not FARM_MONITOR_CAMERA:
                        farm_camera_ok = False
                        farm_camera_error = "No USB Farm Monitor camera detected"
                        time.sleep(2.0)
                        continue
                # Route through _open_video_source so any string accepted by
                # --security-cam also works for FarmMonitor: /dev/video0, rpi,
                # csi, an integer index, rtsp://…, http://….
                cap = _open_video_source(FARM_MONITOR_CAMERA) or cv2.VideoCapture(FARM_MONITOR_CAMERA)
                # MJPG + V4L2 tuning is only meaningful for USB capture devices;
                # RTSP / HTTP / CSI streams ignore most of these properties safely.
                try:
                    cap.set(cv2.CAP_PROP_FOURCC, cv2.VideoWriter_fourcc(*"MJPG"))
                    cap.set(cv2.CAP_PROP_FRAME_WIDTH, FARM_MONITOR_WIDTH)
                    cap.set(cv2.CAP_PROP_FRAME_HEIGHT, FARM_MONITOR_HEIGHT)
                    cap.set(cv2.CAP_PROP_FPS, FARM_MONITOR_FPS)
                    cap.set(cv2.CAP_PROP_AUTO_WB, 1)
                    cap.set(cv2.CAP_PROP_BRIGHTNESS, FARM_MONITOR_BRIGHTNESS)
                    cap.set(cv2.CAP_PROP_CONTRAST, FARM_MONITOR_CONTRAST)
                    cap.set(cv2.CAP_PROP_SATURATION, FARM_MONITOR_SATURATION)
                except Exception:
                    pass
                if not cap.isOpened():
                    farm_camera_ok = False
                    farm_camera_error = f"Cannot open {FARM_MONITOR_CAMERA}"
                    time.sleep(2.0)
                    continue

            ok, frame = cap.read()
            if not ok or frame is None:
                farm_camera_ok = False
                farm_camera_error = "Camera read failed"
                cap.release()
                cap = None
                time.sleep(1.0)
                continue

            farm_camera_ok = True
            farm_camera_error = ""
            _, jpeg = cv2.imencode(".jpg", frame, [cv2.IMWRITE_JPEG_QUALITY, FARM_MONITOR_JPEG_QUALITY])
            with farm_frame_lock:
                farm_frame_bgr = frame.copy()
                farm_latest_jpeg = jpeg.tobytes()
                farm_frame_seq += 1
            time.sleep(interval)
        except Exception as e:
            farm_camera_ok = False
            farm_camera_error = str(e)
            try:
                if cap is not None:
                    cap.release()
            except Exception:
                pass
            cap = None
            time.sleep(2.0)


def _gen_farm_frames():
    last_seq = -1
    idle_sleep = max(0.03, 1.0 / max(1.0, FARM_MONITOR_FPS * 2.0))
    while True:
        with farm_frame_lock:
            frame = farm_latest_jpeg
            seq = farm_frame_seq
        if frame and seq != last_seq:
            last_seq = seq
            yield (b"--frame\r\nContent-Type: image/jpeg\r\n\r\n" + frame + b"\r\n")
        else:
            time.sleep(idle_sleep)


def _is_blurry(frame_bgr) -> bool:
    gray = cv2.cvtColor(frame_bgr, cv2.COLOR_BGR2GRAY)
    return float(cv2.Laplacian(gray, cv2.CV_64F).var()) < FARM_MONITOR_BLUR_VAR


def _capture_farm_batch(cycle_dir: Path, cycle_idx: int):
    source_dir = cycle_dir / "source"
    source_dir.mkdir(parents=True, exist_ok=True)
    usable = []
    skipped = 0
    candidates = []
    fallback_used = 0
    for i in range(1, FARM_MONITOR_BATCH_FRAMES + 1):
        _farm_status_update(
            state="scanning",
            stage="capture",
            current_cycle=cycle_idx,
            total_cycles=FARM_MONITOR_SCAN_CYCLES,
            target_frames=FARM_MONITOR_BATCH_FRAMES,
            captured_frames=i,
            usable_frames=len(usable),
            skipped_frames=skipped,
            fallback_quality_frames=fallback_used,
            analyzing_model="",
            message=f"Capturing cycle {cycle_idx}/{FARM_MONITOR_SCAN_CYCLES}: frame {i}/{FARM_MONITOR_BATCH_FRAMES}",
        )
        with farm_frame_lock:
            frame = None if farm_frame_bgr is None else farm_frame_bgr.copy()
        if frame is None:
            skipped += 1
            time.sleep(FARM_MONITOR_CAPTURE_GAP)
            continue
        gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
        blur_score = float(cv2.Laplacian(gray, cv2.CV_64F).var())
        candidates.append((blur_score, i, frame))
        if blur_score < FARM_MONITOR_BLUR_VAR:
            skipped += 1
            time.sleep(FARM_MONITOR_CAPTURE_GAP)
            continue
        out = source_dir / f"source_{i:03d}.jpg"
        cv2.imwrite(str(out), frame, [cv2.IMWRITE_JPEG_QUALITY, 92])
        usable.append(out)
        _farm_status_update(
            usable_frames=len(usable),
            skipped_frames=skipped,
            message=f"Captured {len(usable)} usable frame(s); skipped {skipped} blurry/unavailable frame(s)",
        )
        time.sleep(FARM_MONITOR_CAPTURE_GAP)
    if not usable and candidates:
        # If lighting/camera quality is poor, analyze the least-bad frames rather
        # than returning no result. The event ratio still protects against noise.
        fallback_count = min(len(candidates), max(1, min(5, FARM_MONITOR_BATCH_FRAMES // 3)))
        for blur_score, i, frame in sorted(candidates, key=lambda x: x[0], reverse=True)[:fallback_count]:
            out = source_dir / f"source_{i:03d}_fallback.jpg"
            cv2.imwrite(str(out), frame, [cv2.IMWRITE_JPEG_QUALITY, 92])
            usable.append(out)
            fallback_used += 1
        skipped = max(0, skipped - fallback_used)
    _farm_status_update(
        usable_frames=len(usable),
        skipped_frames=skipped,
        fallback_quality_frames=fallback_used,
        message=f"Capture cycle {cycle_idx} complete: {len(usable)} usable, {skipped} skipped",
    )
    return usable, skipped, fallback_used


def _write_batch_video(frame_paths, video_path: Path) -> bool:
    if not frame_paths:
        return False
    first = cv2.imread(str(frame_paths[0]))
    if first is None:
        return False
    h, w = first.shape[:2]
    writer = cv2.VideoWriter(str(video_path), cv2.VideoWriter_fourcc(*"MJPG"), max(1.0, FARM_MONITOR_FPS), (w, h))
    if not writer.isOpened():
        return False
    for path in frame_paths:
        frame = cv2.imread(str(path))
        if frame is None:
            continue
        if frame.shape[:2] != (h, w):
            frame = cv2.resize(frame, (w, h))
        writer.write(frame)
    writer.release()
    return True


def _run_farm_model(model_name: str, video_path: Path, cycle_dir: Path, expected_frames: int):
    if model_name == "disease":
        pt = FARM_MONITOR_DISEASE_PT
        size = "512"
        conf = FARM_MONITOR_DISEASE_CONF
    else:
        pt = FARM_MONITOR_RIPENESS_PT
        size = "640"
        conf = FARM_MONITOR_RIPENESS_CONF
    out_dir = cycle_dir / model_name
    summary_path = cycle_dir / f"{model_name}_summary.json"
    cmd = [
        sys.executable, str(FARM_MONITOR_SCAN_SCRIPT),
        "--model-name", model_name,
        "--pt", str(pt),
        "--input-video", str(video_path),
        "--output-dir", str(out_dir),
        "--expected-frames", str(expected_frames),
        "--summary-json", str(summary_path),
        "--conf", str(conf),
        "--width", size,
        "--height", size,
        "--fps", str(int(max(1, FARM_MONITOR_FPS))),
    ]
    try:
        proc = subprocess.run(cmd, capture_output=True, text=True, timeout=240)
        if not summary_path.exists():
            return {
                "model": model_name,
                "error": f"scanner exited {proc.returncode}",
                "stdout": proc.stdout[-1200:],
                "stderr": proc.stderr[-1600:],
                "frames": [],
            }
        data = json.loads(summary_path.read_text(encoding="utf-8"))
        data["returncode"] = proc.returncode
        if proc.returncode != 0:
            data["error"] = proc.stderr[-1600:] or proc.stdout[-1200:]
        return data
    except Exception as e:
        return {"model": model_name, "error": str(e), "frames": []}


def _disease_positive(det: dict) -> bool:
    label = str(det.get("label", "")).lower()
    return bool(label) and "healthy" not in label and float(det.get("confidence", 0)) >= FARM_MONITOR_DISEASE_CONF


def _ripeness_positive(det: dict) -> bool:
    label = str(det.get("label", "")).lower()
    if not label or float(det.get("confidence", 0)) < FARM_MONITOR_RIPENESS_CONF:
        return False
    if "unripe" in label or "green" in label or "white" in label:
        return False
    return "ripe" in label or "flower" in label or "turning" in label or "red" in label


def _fruit_detected(det: dict) -> bool:
    label = str(det.get("label", "")).lower()
    return bool(label) and any(term in label for term in ("fruit", "ripe", "turning", "flower"))


def _box_area_ratio(det: dict) -> float:
    try:
        x1, y1, x2, y2 = [float(v) for v in det.get("bbox", [])[:4]]
        return max(0.0, x2 - x1) * max(0.0, y2 - y1)
    except Exception:
        return 0.0


def _box_iou(a: dict, b: dict) -> float:
    try:
        ax1, ay1, ax2, ay2 = [float(v) for v in a.get("bbox", [])[:4]]
        bx1, by1, bx2, by2 = [float(v) for v in b.get("bbox", [])[:4]]
    except Exception:
        return 0.0
    ix1, iy1 = max(ax1, bx1), max(ay1, by1)
    ix2, iy2 = min(ax2, bx2), min(ay2, by2)
    inter = max(0.0, ix2 - ix1) * max(0.0, iy2 - iy1)
    area_a = max(0.0, ax2 - ax1) * max(0.0, ay2 - ay1)
    area_b = max(0.0, bx2 - bx1) * max(0.0, by2 - by1)
    return inter / max(area_a + area_b - inter, 1e-6)


def _looks_like_fruit_surface_false_alarm(disease_det: dict, ripeness_dets: list[dict]) -> bool:
    """Suppress immature-fruit seed dimples being counted as leaf disease."""
    label = str(disease_det.get("label", "")).lower()
    conf = float(disease_det.get("confidence", 0))
    if "angular leafspot" not in label:
        return False
    area = _box_area_ratio(disease_det)
    if area > 320000:
        return True
    if conf >= 0.85:
        return False
    fruit_dets = [d for d in ripeness_dets if _fruit_detected(d)]
    if not fruit_dets:
        return False
    return any(_box_iou(disease_det, r) > 0.20 or area > 180000 for r in fruit_dets)


def _cycle_fused_counts(cycle: dict) -> tuple[int, int, dict | None, dict | None]:
    disease_by_idx = {f.get("index"): f for f in cycle.get("disease", {}).get("frames", [])}
    ripeness_by_idx = {f.get("index"): f for f in cycle.get("ripeness", {}).get("frames", [])}
    frame_ids = sorted(set(disease_by_idx) | set(ripeness_by_idx))
    disease_frames = 0
    ripeness_frames = 0
    disease_best = None
    ripeness_best = None
    for idx in frame_ids:
        disease_frame = disease_by_idx.get(idx, {})
        ripeness_frame = ripeness_by_idx.get(idx, {})
        ripeness_dets = ripeness_frame.get("detections", [])
        valid_disease = [
            d for d in disease_frame.get("detections", [])
            if _disease_positive(d) and not _looks_like_fruit_surface_false_alarm(d, ripeness_dets)
        ]
        valid_ripeness = [d for d in ripeness_dets if _ripeness_positive(d)]
        if valid_disease:
            disease_frames += 1
        if valid_ripeness:
            ripeness_frames += 1
        for det in valid_disease:
            score = float(det.get("confidence", 0))
            if disease_best is None or score > disease_best["confidence"]:
                disease_best = {
                    "confidence": score,
                    "label": det.get("label", "unknown"),
                    "frame": disease_frame.get("annotated"),
                    "bbox": det.get("bbox"),
                }
        for det in valid_ripeness:
            score = float(det.get("confidence", 0))
            if ripeness_best is None or score > ripeness_best["confidence"]:
                ripeness_best = {
                    "confidence": score,
                    "label": det.get("label", "unknown"),
                    "frame": ripeness_frame.get("annotated"),
                    "bbox": det.get("bbox"),
                }
    return disease_frames, ripeness_frames, disease_best, ripeness_best


def _positive_frame_count(summary: dict, pred) -> int:
    return sum(1 for frame in summary.get("frames", []) if any(pred(d) for d in frame.get("detections", [])))


def _best_frame(summary: dict, pred):
    best = None
    for frame in summary.get("frames", []):
        for det in frame.get("detections", []):
            if not pred(det):
                continue
            score = float(det.get("confidence", 0))
            if best is None or score > best["confidence"]:
                best = {
                    "confidence": score,
                    "label": det.get("label", "unknown"),
                    "frame": frame.get("annotated"),
                    "bbox": det.get("bbox"),
                }
    return best


def _farm_monitor_decide(cycles: list[dict]):
    usable = sum(c.get("usable_frames", 0) for c in cycles)
    disease_frames = 0
    ripeness_frames = 0
    disease_ratio = disease_frames / usable if usable else 0.0
    ripeness_ratio = ripeness_frames / usable if usable else 0.0
    disease_best = None
    ripeness_best = None
    for c in cycles:
        df, rf, db, rb = _cycle_fused_counts(c)
        disease_frames += df
        ripeness_frames += rf
        if db and (disease_best is None or db["confidence"] > disease_best["confidence"]):
            disease_best = db
        if rb and (ripeness_best is None or rb["confidence"] > ripeness_best["confidence"]):
            ripeness_best = rb
    disease_ratio = disease_frames / usable if usable else 0.0
    ripeness_ratio = ripeness_frames / usable if usable else 0.0
    # Event threshold is frame-level, not confidence-level: at least 50% of
    # usable frames must agree before anything is stored or emailed.
    disease_event = disease_ratio >= FARM_MONITOR_EVENT_RATIO
    ripeness_event = ripeness_ratio >= FARM_MONITOR_EVENT_RATIO

    # Prevent false harvest alerts from diseased fruit/leaf frames. If the
    # disease model sees a strong plant-health warning but not enough frames for
    # a sustained disease event, suppress harvest instead of emailing/storing a
    # misleading "ready to harvest" event.
    disease_best_conf = float((disease_best or {}).get("confidence", 0) or 0)
    disease_conflict = bool(disease_best) and (
        disease_ratio >= max(0.25, FARM_MONITOR_EVENT_RATIO * 0.70)
        or disease_best_conf >= 0.80
    )

    if disease_event and ripeness_event:
        event_type = "disease_and_ripeness"
        label = "Plant Health Alert + Harvest Readiness"
        message = "Sustained disease signs and harvest-readiness signs were both detected."
    elif disease_event:
        event_type = "disease"
        label = "Plant Health Alert"
        message = "Sustained plant disease signs were detected."
    elif ripeness_event and not disease_conflict:
        event_type = "ripeness"
        label = "Harvest Readiness"
        message = "Sustained ripe/flowering fruit signs were detected."
    elif ripeness_event and disease_conflict:
        event_type = "clear"
        label = "No Sustained Event"
        message = "Harvest alert suppressed because plant-health warning signs were also detected below the sustained-event threshold."
    else:
        event_type = "clear"
        label = "No Sustained Event"
        message = "No sustained disease or harvest-readiness event was detected."
    return {
        "event_type": event_type,
        "label": label,
        "message": message,
        "usable_frames": usable,
        "disease_frames": disease_frames,
        "ripeness_frames": ripeness_frames,
        "disease_ratio": round(disease_ratio, 3),
        "ripeness_ratio": round(ripeness_ratio, 3),
        "disease_best": disease_best,
        "ripeness_best": ripeness_best,
        "cycles": cycles,
    }


def _save_farm_monitor_event(result: dict):
    if result.get("event_type") == "clear":
        return None
    ts = datetime.now()
    folder = STORAGE_PATH / ts.strftime("%Y") / ts.strftime("%m") / ts.strftime("%d") / ts.strftime("%H-%M-%S")
    folder.mkdir(parents=True, exist_ok=True)
    meta = {
        "label": f"FarmMonitor: {result['label']}",
        "conf": max(result.get("disease_ratio", 0), result.get("ripeness_ratio", 0)),
        "time": ts.isoformat(),
        "event_type": result.get("event_type"),
        "message": result.get("message"),
        "usable_frames": result.get("usable_frames"),
        "disease_ratio": result.get("disease_ratio"),
        "ripeness_ratio": result.get("ripeness_ratio"),
    }
    saved_images = []
    attachments = []
    for key in ("disease_best", "ripeness_best"):
        best = result.get(key)
        if not best or not best.get("frame"):
            continue
        src = Path(best["frame"])
        if not src.exists():
            continue
        tmp = folder / f"{key}.tmp.jpg"
        shutil.copy2(src, tmp)
        hashed = folder / _opaque_hashed_filename(tmp)
        tmp.replace(hashed)
        saved_images.append(_public_storage_name(hashed))
        attachments.append(hashed)
        meta[key] = {"label": best.get("label"), "confidence": round(best.get("confidence", 0), 3)}
    if saved_images:
        meta["images"] = saved_images
    (folder / "meta.json").write_text(json.dumps(meta, indent=2), encoding="utf-8")
    return {"folder": str(folder), "attachments": attachments, "meta": meta}


def _farm_monitor_email_html(result: dict):
    event = result.get("label", "Farm Update")
    message = result.get("message", "")
    disease_pct = round(result.get("disease_ratio", 0) * 100)
    ripe_pct = round(result.get("ripeness_ratio", 0) * 100)
    dashboard_url = _MAIL_CFG.get('app', {}).get('dashboard_url', 'http://raspberrypi:8000')
    badge = "#dc2626" if result.get("event_type") == "disease" else "#0d8a78"
    if result.get("event_type") == "disease_and_ripeness":
        badge = "#f59e0b"
    return f"""<!doctype html>
<html><body style="margin:0;background:#eef8f5;font-family:Arial,sans-serif;color:#123">
<div style="max-width:680px;margin:0 auto;padding:24px">
  <div style="background:#ffffff;border:1px solid #cde9e3;border-radius:22px;overflow:hidden;box-shadow:0 18px 50px rgba(13,138,120,.14)">
    <div style="padding:22px 26px;background:linear-gradient(135deg,#0d8a78,#18c7a8);color:white">
      <div style="font-size:13px;letter-spacing:2px;text-transform:uppercase;opacity:.82">AIgriculture Farm Monitor</div>
      <div style="font-size:26px;font-weight:800;margin-top:6px">{event}</div>
    </div>
    <div style="padding:24px 26px">
      <p style="font-size:17px;line-height:1.65;margin:0 0 18px">{message}</p>
      <div style="display:flex;gap:12px;flex-wrap:wrap;margin:18px 0">
        <div style="flex:1;min-width:170px;border:1px solid #d7ece8;border-radius:16px;padding:15px;background:#f8fffd">
          <div style="font-size:12px;color:#53726b;text-transform:uppercase;letter-spacing:1px">Plant Health Signal</div>
          <div style="font-size:28px;font-weight:800;color:{badge};margin-top:6px">{disease_pct}%</div>
        </div>
        <div style="flex:1;min-width:170px;border:1px solid #d7ece8;border-radius:16px;padding:15px;background:#f8fffd">
          <div style="font-size:12px;color:#53726b;text-transform:uppercase;letter-spacing:1px">Harvest Signal</div>
          <div style="font-size:28px;font-weight:800;color:#0d8a78;margin-top:6px">{ripe_pct}%</div>
        </div>
      </div>
      <p style="color:#4b6760;line-height:1.6">Best detection frames are attached. Review the dashboard storage for full history.</p>
      <a href="{dashboard_url}" style="display:inline-block;background:#0d8a78;color:white;text-decoration:none;font-weight:700;border-radius:999px;padding:12px 18px">Open Dashboard</a>
    </div>
  </div>
</div>
</body></html>"""


def _queue_farm_monitor_email(result: dict, attachments):
    if result.get("event_type") == "clear":
        return
    event_type = result.get("event_type", "ripeness")
    disease_best = result.get("disease_best") or {}
    ripeness_best = result.get("ripeness_best") or {}

    if event_type == "disease_and_ripeness":
        message = "Harvest signs are present, but plant health also needs attention."
        rows = [
            f"{ripeness_best.get('label', 'Harvest signal')}|Seen|Review fruit",
            f"{disease_best.get('label', 'Plant health concern')}|Seen|Inspect plant",
            "Farm action|Needs review|Open dashboard",
        ]
    elif event_type == "disease":
        message = "Plant health needs attention. Review the attached marked picture."
        rows = [
            f"{disease_best.get('label', 'Plant health concern')}|Seen|Inspect plant",
            "Harvest update|Not the priority|Check health first",
        ]
    else:
        message = "Good news: the plant is showing ready-to-harvest fruit."
        rows = [
            f"{ripeness_best.get('label', 'Ripe fruit')}|Seen|Harvest now",
            "Plant health update|No issue|Keep monitoring",
        ]

    _queue_designer_email(
        event_type,
        title="Your field update is ready",
        message=message,
        label=(ripeness_best.get("label") or disease_best.get("label") or result.get("label", "Farm update")),
        disease_ratio=float(result.get("disease_ratio", 0) or 0),
        ripeness_ratio=float(result.get("ripeness_ratio", 0) or 0),
        images=attachments,
        rows=rows,
    )


def _cleanup_old_farm_scans(keep: int = 8):
    try:
        if not FARM_MONITOR_WORK.exists():
            return
        scans = sorted([p for p in FARM_MONITOR_WORK.iterdir() if p.is_dir() and p.name.startswith("scan_")])
        for old in scans[:-keep]:
            shutil.rmtree(old, ignore_errors=True)
    except Exception as e:
        print(f"[WARN] FarmMonitor cleanup failed: {e}")


def run_farm_monitor_scan(manual: bool = False):
    if not farm_scan_lock.acquire(blocking=False):
        _farm_status_update(state="scanning", message="Scan already running")
        return
    try:
        started = datetime.now()
        _ensure_writable_dir(FARM_MONITOR_WORK, "Farm Monitor work folder")
        scan_dir = FARM_MONITOR_WORK / started.strftime("scan_%Y%m%d_%H%M%S")
        scan_dir.mkdir(parents=True, exist_ok=True)
        _farm_status_update(
            state="scanning",
            stage="starting",
            message="Starting Farm Monitor scan",
            last_scan_at=started.isoformat(),
            last_result=None,
            total_cycles=FARM_MONITOR_SCAN_CYCLES,
            current_cycle=0,
            target_frames=FARM_MONITOR_BATCH_FRAMES,
            captured_frames=0,
            usable_frames=0,
            skipped_frames=0,
            fallback_quality_frames=0,
            analyzing_model="",
            disease_frames=0,
            ripeness_frames=0,
            disease_ratio=0,
            ripeness_ratio=0,
        )
        cycles = []
        for cycle_idx in range(1, FARM_MONITOR_SCAN_CYCLES + 1):
            cycle_dir = scan_dir / f"cycle_{cycle_idx}"
            cycle_dir.mkdir(parents=True, exist_ok=True)
            usable, skipped, fallback_used = _capture_farm_batch(cycle_dir, cycle_idx)
            video_path = cycle_dir / "batch.avi"
            cycle = {
                "cycle": cycle_idx,
                "usable_frames": len(usable),
                "skipped_frames": skipped,
                "fallback_quality_frames": fallback_used,
            }
            if not _write_batch_video(usable, video_path):
                cycle["error"] = "No usable camera frames for this cycle"
                cycles.append(cycle)
                continue
            _farm_status_update(
                state="scanning",
                stage="disease_model",
                current_cycle=cycle_idx,
                analyzing_model="Plant Health model",
                message=f"Running Plant Health model on cycle {cycle_idx}/{FARM_MONITOR_SCAN_CYCLES}",
            )
            cycle["disease"] = _run_farm_model("disease", video_path, cycle_dir, len(usable))
            raw_disease = _positive_frame_count(cycle["disease"], _disease_positive)
            _farm_status_update(
                disease_frames=raw_disease,
                analyzing_model="Harvest Readiness model",
                stage="ripeness_model",
                message=f"Plant Health model complete: {raw_disease}/{len(usable)} frame(s) showed warning signs",
            )
            cycle["ripeness"] = _run_farm_model("ripeness", video_path, cycle_dir, len(usable))
            df, rf, db, rb = _cycle_fused_counts(cycle)
            _farm_status_update(
                stage="cycle_summary",
                analyzing_model="",
                disease_frames=df,
                ripeness_frames=rf,
                disease_ratio=round(df / len(usable), 3) if usable else 0,
                ripeness_ratio=round(rf / len(usable), 3) if usable else 0,
                message=f"Cycle {cycle_idx} complete: health warning {df}/{len(usable)}, harvest signal {rf}/{len(usable)}",
            )
            cycles.append(cycle)

        _farm_status_update(stage="decision", analyzing_model="", message="Combining scan results and deciding whether this is an event")
        result = _farm_monitor_decide(cycles)
        result["manual"] = manual
        result["scan_dir"] = str(scan_dir)
        result["completed_at"] = datetime.now().isoformat()
        saved = _save_farm_monitor_event(result)
        if saved:
            _queue_farm_monitor_email(result, saved.get("attachments", []))
        elif result.get("event_type") == "clear":
            # Below-threshold scans are not evidence. Remove their temporary
            # frames immediately so they cannot appear as stored farm events.
            shutil.rmtree(scan_dir, ignore_errors=True)
        if result.get("event_type") != "clear":
            with _hist_lock:
                detect_hist.append({
                    "t": time.time(),
                    "label": result.get("label", "Farm Monitor"),
                    "conf": max(result.get("disease_ratio", 0), result.get("ripeness_ratio", 0)),
                    "event_type": result.get("event_type"),
                })
        _cleanup_old_farm_scans()
        _farm_status_update(
            state="idle",
            stage="complete",
            message=result["message"],
            last_result=result,
            current_cycle=FARM_MONITOR_SCAN_CYCLES,
            captured_frames=FARM_MONITOR_BATCH_FRAMES,
            usable_frames=result.get("usable_frames", 0),
            disease_frames=result.get("disease_frames", 0),
            ripeness_frames=result.get("ripeness_frames", 0),
            disease_ratio=result.get("disease_ratio", 0),
            ripeness_ratio=result.get("ripeness_ratio", 0),
            analyzing_model="",
        )
    except Exception as e:
        _farm_status_update(state="error", stage="error", message=f"Farm Monitor scan failed: {e}", analyzing_model="")
        print(f"[WARN] FarmMonitor scan failed: {e}")
    finally:
        farm_scan_lock.release()


def farm_monitor_scheduler_loop():
    next_scan = time.time() + FARM_MONITOR_SCAN_INTERVAL
    _farm_status_update(next_scan_at=datetime.fromtimestamp(next_scan).isoformat())
    while True:
      try:
        wait_for = max(1.0, min(30.0, next_scan - time.time()))
        requested = farm_scan_request.wait(wait_for)
        if requested or time.time() >= next_scan:
            farm_scan_request.clear()
            run_farm_monitor_scan(manual=requested)
            next_scan = time.time() + FARM_MONITOR_SCAN_INTERVAL
            _farm_status_update(next_scan_at=datetime.fromtimestamp(next_scan).isoformat())
      except Exception as _e:
        print(f"[CRITICAL] farm_monitor_scheduler_loop crashed: {_e}", flush=True)
        time.sleep(30.0)

# ── Database helpers ───────────────────────────────────────────────────────────
def _db_conn():
    return pymysql.connect(
        host=DB_HOST, port=DB_PORT, user=DB_USER, password=DB_PASS,
        database=DB_NAME, charset="utf8mb4",
        cursorclass=pymysql.cursors.DictCursor,
        connect_timeout=5,
    )

def _ensure_user_columns(cur):
    """Add role/profile columns for demo users without rebuilding the table."""
    cur.execute("SHOW COLUMNS FROM users")
    cols = {row.get("Field") for row in cur.fetchall()}
    if "role" not in cols:
        cur.execute("ALTER TABLE users ADD COLUMN role VARCHAR(20) NOT NULL DEFAULT 'admin'")
    if "display_name" not in cols:
        cur.execute("ALTER TABLE users ADD COLUMN display_name VARCHAR(80) NULL")
    if "avatar_url" not in cols:
        cur.execute("ALTER TABLE users ADD COLUMN avatar_url VARCHAR(255) NULL")

def _db_init():
    """Create database, user table, and seed default admin if needed."""
    if not MYSQL_AVAILABLE:
        hailo_logger.warning("pymysql not available — auth disabled")
        return
    try:
        conn = _db_conn()
        with conn:
            with conn.cursor() as cur:
                cur.execute("""
                    CREATE TABLE IF NOT EXISTS users (
                        id              INT AUTO_INCREMENT PRIMARY KEY,
                        username        VARCHAR(50) UNIQUE NOT NULL,
                        password_hash   VARCHAR(255) NOT NULL,
                        failed_attempts INT DEFAULT 0,
                        locked_until    DATETIME NULL,
                        last_login      DATETIME NULL,
                        created_at      DATETIME DEFAULT CURRENT_TIMESTAMP
                    ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4
                """)
                cur.execute("""
                    CREATE TABLE IF NOT EXISTS sessions (
                        id          INT AUTO_INCREMENT PRIMARY KEY,
                        username    VARCHAR(50) NOT NULL,
                        jti         CHAR(64) UNIQUE NOT NULL,
                        issued_at   DATETIME NOT NULL,
                        expires_at  DATETIME NOT NULL,
                        revoked     TINYINT(1) DEFAULT 0,
                        INDEX idx_jti (jti)
                    ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4
                """)
                conn.commit()
                _ensure_user_columns(cur)
                conn.commit()
                # Seed default admin if table is empty.
                # If ADMIN_PASS is unset/blank, generate a random one and print
                # it loudly so the operator can copy it from systemd logs.
                cur.execute("SELECT COUNT(*) as n FROM users")
                if cur.fetchone()["n"] == 0:
                    seed_user = os.getenv("ADMIN_USER", "admin").strip() or "admin"
                    seed_pass = os.getenv("ADMIN_PASS", "").strip()
                    auto_generated = False
                    if not seed_pass:
                        import secrets as _secrets
                        seed_pass = _secrets.token_urlsafe(12)
                        auto_generated = True
                    if BCRYPT_AVAILABLE:
                        ph = _pwd_ctx.hash(seed_pass)
                    else:
                        ph = "BCRYPT_UNAVAILABLE"
                    # Seed with neutral defaults derived from the username — the
                    # operator can edit display_name / avatar from Settings →
                    # Profile and we MUST NOT overwrite their choices on later
                    # boots.
                    cur.execute(
                        "INSERT INTO users (username, password_hash, role, display_name, avatar_url) VALUES (%s, %s, %s, %s, %s)",
                        (seed_user, ph, ADMIN_ROLE, seed_user, _asset_url("farmer.png"))
                    )
                    conn.commit()
                    if auto_generated:
                        hailo_logger.info("=" * 58)
                        hailo_logger.info(
                            f"  Default user '{seed_user}' seeded — initial password:"
                        )
                        hailo_logger.info(f"      {seed_pass}")
                        hailo_logger.info(
                            "  Log in and change it from Settings → Profile."
                        )
                        hailo_logger.info("=" * 58)
                    else:
                        hailo_logger.info(
                            f"Default user '{seed_user}' seeded in DB — "
                            f"please change the password from the dashboard on first login."
                        )
                # Refresh ONLY the role of the configured admin user. We do not
                # overwrite display_name / avatar_url here because the operator
                # may have customised them — that's a profile preference, not a
                # boot-time invariant.
                cur.execute(
                    "UPDATE users SET role=%s WHERE username=%s",
                    (ADMIN_ROLE, os.getenv("ADMIN_USER", "admin"))
                )
        hailo_logger.info("Database tables ready")
    except Exception as e:
        hailo_logger.error(f"DB init error: {e}")

def _verify_credentials(username: str, password: str):
    """Returns user row dict on success, None on failure."""
    if not MYSQL_AVAILABLE or not BCRYPT_AVAILABLE:
        return None
    try:
        conn = _db_conn()
        with conn:
            with conn.cursor() as cur:
                cur.execute(
                    "SELECT * FROM users WHERE username=%s", (username,)
                )
                user = cur.fetchone()
                if not user:
                    return None
                # Check account lock
                if user["locked_until"]:
                    from datetime import timezone
                    if datetime.now() < user["locked_until"]:
                        return None      # still locked
                    # Expired lock — reset
                    cur.execute(
                        "UPDATE users SET failed_attempts=0, locked_until=NULL WHERE id=%s",
                        (user["id"],)
                    )
                    conn.commit()
                if not _pwd_ctx.verify(password, user["password_hash"]):
                    # Increment failed attempts
                    new_count = user["failed_attempts"] + 1
                    if new_count >= MAX_ATTEMPTS:
                        from datetime import timedelta as _td
                        lock_until = datetime.now() + _td(seconds=LOCKOUT_SECS)
                        cur.execute(
                            "UPDATE users SET failed_attempts=%s, locked_until=%s WHERE id=%s",
                            (new_count, lock_until, user["id"])
                        )
                    else:
                        cur.execute(
                            "UPDATE users SET failed_attempts=%s WHERE id=%s",
                            (new_count, user["id"])
                        )
                    conn.commit()
                    return None
                # Success — reset failed count, update last_login
                cur.execute(
                    "UPDATE users SET failed_attempts=0, locked_until=NULL, last_login=%s WHERE id=%s",
                    (datetime.now(), user["id"])
                )
                conn.commit()
                return user
    except Exception as e:
        hailo_logger.error(f"DB verify error: {e}")
        return None

def _create_token(username: str) -> tuple[str, str]:
    """Returns (jwt_string, jti)."""
    from datetime import timezone
    jti = _secrets.token_hex(32)
    exp = datetime.now(timezone.utc) + timedelta(hours=JWT_EXPIRE_HRS)
    payload = {"sub": username, "jti": jti, "exp": exp}
    token = _jwt.encode(payload, JWT_SECRET, algorithm=JWT_ALGO)
    # Record in DB
    try:
        conn = _db_conn()
        with conn:
            with conn.cursor() as cur:
                cur.execute(
                    "INSERT INTO sessions (username, jti, issued_at, expires_at) VALUES (%s,%s,%s,%s)",
                    (username, jti, datetime.now(), datetime.now() + timedelta(hours=JWT_EXPIRE_HRS))
                )
            conn.commit()
    except Exception as e:
        hailo_logger.error(f"Session insert error: {e}")
    return token, jti

def _revoke_token(jti: str):
    """Mark a session as revoked (logout)."""
    try:
        conn = _db_conn()
        with conn:
            with conn.cursor() as cur:
                cur.execute("UPDATE sessions SET revoked=1 WHERE jti=%s", (jti,))
            conn.commit()
    except Exception as e:
        hailo_logger.error(f"Session revoke error: {e}")

def _is_token_revoked(jti: str) -> bool:
    try:
        conn = _db_conn()
        with conn:
            with conn.cursor() as cur:
                cur.execute("SELECT revoked FROM sessions WHERE jti=%s", (jti,))
                row = cur.fetchone()
                return row is None or bool(row["revoked"])
    except Exception as _e:
        hailo_logger.error(f"DB token-revocation check failed: {_e} — treating as revoked")
        return True   # fail closed

# ── Rate limiter ───────────────────────────────────────────────────────────────
def _check_rate_limit(ip: str) -> bool:
    """Returns True if allowed, False if rate-limited."""
    now = time.time()
    with _rate_lock:
        entry = _rate_map.get(ip, {"count": 0, "locked_until": 0})
        if entry["locked_until"] > now:
            return False
        if entry["locked_until"] and entry["locked_until"] <= now:
            entry = {"count": 0, "locked_until": 0}
        entry["count"] = entry.get("count", 0) + 1
        if entry["count"] > MAX_ATTEMPTS:
            entry["locked_until"] = now + LOCKOUT_SECS
            entry["count"] = 0
        _rate_map[ip] = entry
        return entry["locked_until"] == 0

def _reset_rate_limit(ip: str):
    with _rate_lock:
        _rate_map.pop(ip, None)

# ── Auth dependency ────────────────────────────────────────────────────────────
class _AuthRedirectException(Exception):
    """Raised by require_auth to trigger a redirect to /login."""
    pass

NO_STORE_HEADERS = {
    "Cache-Control": "no-store, no-cache, must-revalidate, max-age=0",
    "Pragma": "no-cache",
    "Expires": "0",
}

def _no_store(resp):
    resp.headers.update(NO_STORE_HEADERS)
    return resp

SECURITY_HEADERS = {
    "X-Content-Type-Options": "nosniff",
    "X-Frame-Options": "DENY",
    "Referrer-Policy": "strict-origin-when-cross-origin",
    "Cross-Origin-Opener-Policy": "same-origin",
    "Permissions-Policy": "camera=(self), microphone=(), geolocation=()",
    "Content-Security-Policy": (
        "default-src 'self'; "
        "script-src 'self' 'unsafe-inline'; "
        "style-src 'self' 'unsafe-inline' https://fonts.googleapis.com; "
        "img-src 'self' data: blob:; "
        "media-src 'self' blob:; "
        "font-src 'self' data: https://fonts.gstatic.com; "
        "connect-src 'self'; "
        "frame-ancestors 'none'; "
        "base-uri 'self'; "
        "object-src 'none'; "
        "form-action 'self'"
    ),
}
_CSP_SKIP_PATHS = {"/docs", "/redoc", "/openapi.json"}
MAX_REQUEST_BYTES = 8 * 1024 * 1024  # 8 MB — anything larger is rejected up-front
UNSAFE_HTTP_METHODS = {"POST", "PUT", "PATCH", "DELETE"}

def _request_scheme(request: Request) -> str:
    forwarded = request.headers.get("x-forwarded-proto", "").split(",", 1)[0].strip().lower()
    if forwarded:
        return forwarded
    if request.headers.get("x-forwarded-ssl", "").lower() == "on":
        return "https"
    return request.url.scheme

def _is_https_request(request: Request) -> bool:
    return _request_scheme(request) == "https"

def _same_origin_request(request: Request, origin: str | None) -> bool:
    if not origin:
        return True
    parsed = urlparse(origin)
    if not parsed.scheme or not parsed.netloc:
        return False
    return parsed.scheme == _request_scheme(request) and parsed.netloc == request.headers.get("host", "")

def _apply_security_headers(resp, request: Request):
    skip_csp = request.url.path in _CSP_SKIP_PATHS
    for key, value in SECURITY_HEADERS.items():
        if skip_csp and key == "Content-Security-Policy":
            continue
        resp.headers.setdefault(key, value)
    if _is_https_request(request):
        resp.headers.setdefault("Strict-Transport-Security", "max-age=31536000; includeSubDomains")
    return resp

def _valid_session_user(request: Request):
    token = request.cookies.get("pmc_token")
    if not token or not JWT_AVAILABLE:
        return None
    try:
        payload = _jwt.decode(token, JWT_SECRET, algorithms=[JWT_ALGO])
    except (_jwt.ExpiredSignatureError, _jwt.InvalidTokenError):
        return None
    if _is_token_revoked(payload.get("jti", "")):
        return None
    return payload.get("sub")

def _get_user_profile(username: str) -> dict:
    # Defaults are derived from the supplied username — we never invent or
    # hardcode display_name / role. The DB lookup below replaces these with the
    # authoritative row when it succeeds.
    profile = {
        "username": username or "",
        "role": ADMIN_ROLE,
        "display_name": username or "",
        "avatar_url": _asset_url("farmer.png"),
    }
    if not username or not MYSQL_AVAILABLE:
        return profile
    try:
        conn = _db_conn()
        with conn:
            with conn.cursor() as cur:
                cur.execute(
                    "SELECT username, role, display_name, avatar_url FROM users WHERE username=%s",
                    (username,),
                )
                row = cur.fetchone()
                if row:
                    profile.update({
                        "username": row.get("username") or username,
                        "role": row.get("role") or ADMIN_ROLE,
                        "display_name": row.get("display_name") or row.get("username") or username,
                        "avatar_url": row.get("avatar_url") or _asset_url("farmer.png"),
                    })
    except Exception as exc:
        hailo_logger.warning(f"user profile lookup failed: {exc}")
    return profile

def _user_permissions(role: str) -> dict:
    is_admin = role == ADMIN_ROLE
    return {
        "view": True,
        "email_signup": True,
        "control": is_admin,
        "irrigation": is_admin,
        "camera_actions": is_admin,
        "settings_write": is_admin,
        "flora_write": is_admin,
    }

def _is_admin_user(username: str) -> bool:
    return _get_user_profile(username).get("role") == ADMIN_ROLE

async def require_auth(request: Request):
    """FastAPI dependency — validates JWT cookie.
    API paths (/api/*, /ws) → 401 JSON on failure.
    All other paths        → redirect to /login on failure.
    """
    from fastapi import HTTPException
    token = request.cookies.get("pmc_token")
    is_api = request.url.path.startswith("/api") or request.url.path.startswith("/ws")

    def _fail():
        if is_api:
            raise HTTPException(status_code=401, detail="Not authenticated")
        raise _AuthRedirectException()

    if not token:
        _fail()
    try:
        payload = _jwt.decode(token, JWT_SECRET, algorithms=[JWT_ALGO])
    except (_jwt.ExpiredSignatureError, _jwt.InvalidTokenError):
        _fail()
    jti = payload.get("jti", "")
    if _is_token_revoked(jti):
        _fail()
    return payload["sub"]

async def require_admin(_user: str = Depends(require_auth)):
    from fastapi import HTTPException
    if not _is_admin_user(_user):
        raise HTTPException(status_code=403, detail="Admin account required for this control action.")
    return _user

# ── FastAPI app ────────────────────────────────────────────────────────────────
@asynccontextmanager
async def lifespan(app_: FastAPI):
    STORAGE_PATH.mkdir(parents=True, exist_ok=True)
    _db_init()
    task = asyncio.create_task(ws_push_task())
    try:
        init_flora(asyncio.get_running_loop())
    except Exception as _fe:
        print(f"[WARN] FLORA startup skipped: {_fe}")
    yield
    task.cancel()

_DOCS_PUBLIC = os.environ.get("AIGRI_PUBLIC_DOCS", "").strip().lower() in {"1", "true", "yes", "on"}
app = FastAPI(
    title="Plant Monitor",
    lifespan=lifespan,
    docs_url="/docs" if _DOCS_PUBLIC else None,
    redoc_url="/redoc" if _DOCS_PUBLIC else None,
    openapi_url="/openapi.json" if _DOCS_PUBLIC else None,
)

@app.middleware("http")
async def request_size_middleware(request: Request, call_next):
    cl = request.headers.get("content-length")
    if cl is not None:
        try:
            if int(cl) > MAX_REQUEST_BYTES:
                return _apply_security_headers(
                    JSONResponse({"ok": False, "error": "request body too large"}, status_code=413),
                    request,
                )
        except ValueError:
            pass
    return await call_next(request)

@app.middleware("http")
async def security_middleware(request: Request, call_next):
    # Keep response hardening headers, but do not block POSTs by Origin here.
    # Farm access can pass through local hostnames, Tailscale, or reverse proxies,
    # so strict Origin/Host matching can break valid login and controls.
    response = await call_next(request)
    return _apply_security_headers(response, request)

def _health_payload():
    return {
        "ok": True,
        "service": "aigriculture",
        "time": datetime.now().isoformat(timespec="seconds"),
        "hailo_available": False,  # CPU build — see main-hailo.py for the Hailo build
        "gpio_available": bool(GPIO_AVAILABLE),
        "i2c_available": bool(I2C_AVAILABLE),
        "storage_ready": STORAGE_PATH.exists() and os.access(STORAGE_PATH, os.W_OK),
        "plants": len(PLANTS),
        "pumps": len(PUMP_PLANTS),
    }

@app.get("/healthz")
def healthz(_user: str = Depends(require_auth)):
    return JSONResponse(_health_payload(), headers={"Cache-Control": "no-store"})

@app.get("/api/health")
def api_health(_user: str = Depends(require_auth)):
    return JSONResponse(_health_payload(), headers={"Cache-Control": "no-store"})

@app.get("/api/me")
def api_me(_user: str = Depends(require_auth)):
    profile = _get_user_profile(_user)
    role = profile.get("role") or ADMIN_ROLE
    return JSONResponse({
        "username": profile.get("username"),
        "display_name": profile.get("display_name"),
        "role": role,
        "avatar_url": profile.get("avatar_url"),
        "permissions": _user_permissions(role),
    }, headers={"Cache-Control": "no-store"})


# ── Notification email API ─────────────────────────────────────────────────────
@app.get("/api/notification_email")
def notification_email_get(_user: str = Depends(require_auth)):
    with _notification_lock:
        email = _notification_email
    return JSONResponse({
        "configured": bool(email),
        "email": email or "",
        "smtp_ready": _smtp_ready(),
    })

@app.post("/api/notification_email")
async def notification_email_set(request: Request, _user: str = Depends(require_auth)):
    global _notification_email
    try:
        data = await request.json()
    except Exception:
        data = {}
    email = str(data.get("email", "")).strip()
    if not _EMAIL_RE.match(email):
        return JSONResponse({"ok": False, "error": "Enter a valid email address"}, status_code=400)
    with _notification_lock:
        _notification_email = email
    subject, text_body, html_body = _subscription_email_html(email)
    _queue_notification_email_html(subject, text_body, html_body, key="email-confirmed-html", min_gap=1.0)
    return JSONResponse({"ok": True, "email": email, "smtp_ready": _smtp_ready()})


# ── Exception handler for auth redirects ──────────────────────────────────────
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request as StarletteRequest

@app.exception_handler(_AuthRedirectException)
async def _auth_redirect_handler(request, exc):
    return _no_store(RedirectResponse(url="/login", status_code=303))

# ── Login page ─────────────────────────────────────────────────────────────────
@app.get("/login", response_class=HTMLResponse)
async def login_page(request: Request):
    if _valid_session_user(request):
        return _no_store(RedirectResponse(url="/", status_code=303))
    lp = BASE_DIR / "design" / "login.html"
    if not lp.exists():
        lp = BASE_DIR / "login.html"  # legacy fallback
    if lp.exists():
        return _no_store(HTMLResponse(_apply_content_hashed_assets(lp.read_text(encoding="utf-8"))))
    return _no_store(HTMLResponse("<h1>login.html not found</h1>", status_code=500))

@app.post("/auth/login")
async def auth_login(request: Request,
                     username: str = Form(...),
                     password: str = Form(...)):
    ip = request.client.host if request.client else "unknown"

    # IP-level rate limit
    if not _check_rate_limit(ip):
        return _no_store(JSONResponse({"ok": False,
                                       "error": "Too many attempts. Try again in 15 minutes."},
                                      status_code=429))

    # Constant-time-ish gate when libs unavailable
    if not MYSQL_AVAILABLE or not BCRYPT_AVAILABLE or not JWT_AVAILABLE:
        return _no_store(JSONResponse({"ok": False,
                                       "error": "Auth backend unavailable — check server logs."},
                                      status_code=503))

    user = await asyncio.get_running_loop().run_in_executor(
        None, _verify_credentials, username.strip(), password
    )
    if not user:
        return _no_store(JSONResponse({"ok": False,
                                       "error": "Invalid credentials."}, status_code=401))

    _reset_rate_limit(ip)
    token, jti = await asyncio.get_running_loop().run_in_executor(
        None, _create_token, user["username"]
    )

    resp = JSONResponse({"ok": True, "username": user["username"]})
    resp.set_cookie(
        key="pmc_token",
        value=token,
        httponly=True,
        samesite="strict",
        max_age=JWT_EXPIRE_HRS * 3600,
        path="/",
        secure=_is_https_request(request),
    )
    return _no_store(resp)

@app.post("/auth/logout")
async def auth_logout(request: Request):
    token = request.cookies.get("pmc_token")
    if token:
        try:
            payload = _jwt.decode(token, JWT_SECRET, algorithms=[JWT_ALGO],
                                  options={"verify_exp": False})
            await asyncio.get_running_loop().run_in_executor(
                None, _revoke_token, payload.get("jti", "")
            )
        except Exception as _e:
            hailo_logger.warning(f"logout: could not revoke token: {_e}")
    resp = RedirectResponse(url="/login", status_code=303)
    resp.delete_cookie("pmc_token", path="/")
    return _no_store(resp)


# ── WebSocket ──────────────────────────────────────────────────────────────────
@app.websocket("/ws")
async def ws_endpoint(websocket: WebSocket):
    # WebSocket auth — read JWT cookie from handshake headers
    from fastapi import HTTPException
    token = websocket.cookies.get("pmc_token")
    if not token:
        await websocket.close(code=1008)
        return
    try:
        payload = _jwt.decode(token, JWT_SECRET, algorithms=[JWT_ALGO])
    except (_jwt.ExpiredSignatureError, _jwt.InvalidTokenError):
        await websocket.close(code=1008)
        return
    if _is_token_revoked(payload.get("jti", "")):
        await websocket.close(code=1008)
        return

    await websocket.accept()
    with _ws_lock:
        _ws_clients.append(websocket)
    try:
        while True:
            await websocket.receive_text()
    except WebSocketDisconnect:
        pass
    finally:
        with _ws_lock:
            if websocket in _ws_clients:
                _ws_clients.remove(websocket)

# ── FLORA Intelligence ────────────────────────────────────────────────────────
_flora_clients: list = []
_flora_lock = threading.Lock()

try:
    import flora_tools
    import flora_agent
    import flora_scheduler
    _FLORA_AVAILABLE = True
except Exception as _fe:  # pragma: no cover
    _FLORA_AVAILABLE = False
    print(f"[WARN] FLORA modules unavailable ({_fe}) — /ws/flora limited to a notice")


async def _flora_broadcast(data: dict):
    """Push one JSON message to every connected FLORA chat client."""
    dead = []
    with _flora_lock:
        clients = list(_flora_clients)
    for ws in clients:
        try:
            await ws.send_json(data)
        except Exception:
            dead.append(ws)
    if dead:
        with _flora_lock:
            for ws in dead:
                if ws in _flora_clients:
                    _flora_clients.remove(ws)


def _flora_get_auto():
    with auto_lock:
        return auto_enabled


def _flora_set_auto(value):
    global auto_enabled
    with auto_lock:
        auto_enabled = bool(value)


def _flora_get_at_farm():
    with at_farm_lock:
        return at_farm


def _flora_set_at_farm(value):
    global at_farm
    with at_farm_lock:
        at_farm = bool(value)


def _flora_camera_status():
    """Live status of both cameras for FLORA's get_camera_status tool."""
    with frame_lock:
        seq1 = frame_seq
    time.sleep(0.5)
    with frame_lock:
        seq2 = frame_seq
        has_frame = latest_jpeg is not None
    security = {
        "enabled": security_cam_on,
        "online": seq2 > seq1,
        "detail": ("paused by you — detection off" if not security_cam_on
                   else ("streaming live" if seq2 > seq1
                         else ("idle (last frame held)" if has_frame else "no signal"))),
        "source": SECURITY_CAMERA_SOURCE or "rpi",
    }
    farm_snap = _farm_status_snapshot()
    farmmonitor = {
        "enabled": farm_cam_on,
        "online": bool(farm_snap.get("camera_ok")),
        "detail": farm_snap.get("camera_error") or "streaming live",
        "scan_state": farm_snap.get("state"),
        "last_result": farm_snap.get("last_result"),
        "next_scan_at": farm_snap.get("next_scan_at"),
    }
    return {"security": security, "farmmonitor": farmmonitor}


def _flora_set_camera(camera: str, on: bool) -> bool:
    """Enable/disable a camera's monitoring. Used by FLORA's set_camera tool and
    the /api/camera endpoint. 'all' toggles both."""
    global security_cam_on, farm_cam_on
    cam = (camera or "all").strip().lower()
    on = bool(on)
    if cam in ("security", "sec", "rpi", "all"):
        security_cam_on = on
    if cam in ("farmmonitor", "farm", "monitor", "usb", "all"):
        farm_cam_on = on
    return on


def _flora_email_images(subject: str, body: str, image_paths: list) -> tuple:
    """Email recent detection snapshots attached directly (not inside a PDF)."""
    with _notification_lock:
        to_email = _notification_email
    if not to_email:
        return (False, "no notification email is saved")
    if not _smtp_ready():
        return (False, "the server email (SMTP) is not configured")
    try:
        _send_email_html_now(to_email, subject, body,
                             f"<p>{html_lib.escape(body)}</p>",
                             attachments=[str(p) for p in (image_paths or [])])
        return (True, to_email)
    except Exception as exc:
        return (False, str(exc))


def _flora_set_notify_email(email: str) -> tuple:
    """Save the notification email address — FLORA settings control."""
    global _notification_email
    email = (email or "").strip()
    if not _EMAIL_RE.match(email):
        return (False, "that doesn't look like a valid email address")
    with _notification_lock:
        _notification_email = email
    return (True, email)


def _flora_test_buzzer() -> tuple:
    """Fire a short test beep on both buzzers — FLORA control."""
    if not BUZZER_AVAILABLE:
        return (False, "the buzzers are not connected yet")
    def _beep():
        for _ in range(3):
            _buzzer_tone(True); time.sleep(BUZZER_ON_S)
            _buzzer_tone(False); time.sleep(BUZZER_OFF_S)
    threading.Thread(target=_beep, daemon=True).start()
    return (True, "beeping now")


def _flora_set_siren(enabled: bool) -> bool:
    """Mute/unmute the intruder siren — FLORA control."""
    global siren_enabled
    siren_enabled = bool(enabled)
    if not siren_enabled:
        _set_siren(False)
    return siren_enabled


# -- FLORA report downloads: short-lived authenticated PDF links -----------------
_flora_reports: dict = {}
_flora_reports_lock = threading.Lock()
_FLORA_REPORT_TTL = 300  # seconds the download link stays valid


def _flora_sweep_reports():
    """Delete report files whose links have expired."""
    cutoff = time.time()
    with _flora_reports_lock:
        dead = [tok for tok, (_p, exp) in _flora_reports.items() if exp < cutoff]
        for tok in dead:
            path, _ = _flora_reports.pop(tok)
            try:
                os.remove(path)
            except OSError:
                pass


def _flora_register_report(path: str) -> str:
    """Register a built PDF report; return its single download token."""
    _flora_sweep_reports()
    token = os.urandom(16).hex()
    with _flora_reports_lock:
        _flora_reports[token] = (path, time.time() + _FLORA_REPORT_TTL)
    return token


@app.get("/api/flora/report/{token}")
async def flora_report_download(token: str, _user: str = Depends(require_auth)):
    """Serve a FLORA-built PDF report while its short-lived link is valid."""
    _flora_sweep_reports()
    with _flora_reports_lock:
        entry = _flora_reports.get(token)
    if not entry or entry[1] < time.time() or not os.path.exists(entry[0]):
        return JSONResponse({"error": "This report link has expired."},
                            status_code=404)
    from fastapi.responses import FileResponse
    return FileResponse(entry[0], media_type="application/pdf",
                        filename=os.path.basename(entry[0]))


def _flora_email_report(subject: str, body: str, pdf_path: str):
    """Email a built PDF report (attached) to the saved notification address.
    Synchronous; returns (ok, detail). Runs inside FLORA's tool executor thread,
    so blocking briefly on SMTP here is fine."""
    with _notification_lock:
        to_email = _notification_email
    if not to_email:
        return (False, "no notification email is saved")
    if not _smtp_ready():
        return (False, "the server email (SMTP) is not configured")
    smtp = _MAIL_CFG.get("smtp", {})
    try:
        msg = EmailMessage()
        msg["Subject"] = subject
        msg["From"] = smtp.get("from_email") or smtp.get("email")
        msg["To"] = to_email
        msg.set_content(body)
        p = Path(pdf_path)
        if p.exists() and p.is_file():
            msg.add_attachment(p.read_bytes(), maintype="application",
                               subtype="pdf", filename=p.name)
        with smtplib.SMTP(smtp.get("host"), int(smtp.get("port", 587)),
                          timeout=25) as server:
            server.starttls()
            server.login(smtp.get("email"), smtp.get("password"))
            server.send_message(msg)
        print(f"[EMAIL] FLORA report sent to {to_email}")
        return (True, to_email)
    except Exception as exc:
        print(f"[WARN] FLORA report email failed: {exc}")
        return (False, str(exc))


def init_flora(loop):
    """Wire FLORA's tools + scheduler to live farm state. Called once from lifespan."""
    if not _FLORA_AVAILABLE:
        return
    sched = flora_scheduler.start()
    flora_scheduler.set_runtime(_flora_broadcast, loop)
    flora_tools.init_shared_state({
        "moisture_vals": moisture_vals, "moisture_lock": moisture_lock,
        "sensor_status": sensor_status, "sensor_lock": sensor_lock,
        "pump_states": pump_states, "pump_lock": pump_lock,
        "manual_pumps": manual_pumps,
        "burst_state": burst_state, "burst_timer": burst_timer,
        "cmd_deadline": cmd_deadline, "CMD_MAX_S": CMD_MAX_S,
        "moisture_hist": moisture_hist, "detect_hist": detect_hist,
        "irr_hist": irr_hist, "hist_lock": _hist_lock,
        "active_alerts": active_alerts,
        "farm_scan_status": farm_scan_status,
        "farm_scan_lock": farm_scan_status_lock,
        "farm_scan_request": farm_scan_request,
        "set_relay": set_relay,
        "get_auto": _flora_get_auto, "set_auto": _flora_set_auto,
        "get_at_farm": _flora_get_at_farm, "set_at_farm": _flora_set_at_farm,
        "camera_status": _flora_camera_status,
        "set_camera": _flora_set_camera,
        "test_buzzer": _flora_test_buzzer,
        "set_siren": _flora_set_siren,
        "email_images": _flora_email_images,
        "set_notify_email": _flora_set_notify_email,
        "PLANTS": PLANTS, "RELAY_PINS": RELAY_PINS,
        "SENSOR_CHANNELS": SENSOR_CHANNELS,
        "TRIGGER_PCT": TRIGGER_PCT, "STOP_PCT": STOP_PCT, "LOCK_PCT": LOCK_PCT,
        "BURST_ON_S": BURST_ON_S, "BURST_WAIT_S": BURST_WAIT_S,
        "STORAGE_PATH": STORAGE_PATH, "scheduler": sched,
        "send_email": lambda subject, body: _queue_notification_email(
            subject, body, key="flora", min_gap=5.0),
        "get_notify_email": lambda: _notification_email,
        "register_report": _flora_register_report,
        "email_report": _flora_email_report,
    })
    print("[INFO] FLORA Intelligence online — 15 tools wired to live farm state")


@app.websocket("/ws/flora")
async def ws_flora(websocket: WebSocket):
    """FLORA Intelligence chat WebSocket — JWT-authenticated."""
    token = websocket.cookies.get("pmc_token")
    if not token:
        await websocket.close(code=1008)
        return
    try:
        payload = _jwt.decode(token, JWT_SECRET, algorithms=[JWT_ALGO])
    except (_jwt.ExpiredSignatureError, _jwt.InvalidTokenError):
        await websocket.close(code=1008)
        return
    if _is_token_revoked(payload.get("jti", "")):
        await websocket.close(code=1008)
        return
    await websocket.accept()
    with _flora_lock:
        _flora_clients.append(websocket)
    try:
        while True:
            data = await websocket.receive_json()
            if _FLORA_AVAILABLE:
                asyncio.create_task(flora_agent.handle_message(data, _flora_broadcast))
            else:
                await websocket.send_json({
                    "type": "response",
                    "content": "FLORA modules are not installed on the server.",
                })
    except WebSocketDisconnect:
        pass
    finally:
        with _flora_lock:
            if websocket in _flora_clients:
                _flora_clients.remove(websocket)


@app.post("/api/flora/chat")
async def flora_chat_api(body: dict, _user: str = Depends(require_auth)):
    """HTTP fallback for FLORA when a reverse proxy blocks WebSocket upgrades."""
    if not _FLORA_AVAILABLE:
        return JSONResponse({
            "ok": False,
            "error": "FLORA modules are not installed on the server.",
        }, status_code=503)

    content = str(body.get("content") or body.get("message") or "").strip()
    mode = str(body.get("mode") or "cloud").strip().lower() or "cloud"
    brief = bool(body.get("brief"))
    if not content:
        return JSONResponse({"ok": False, "error": "Message is empty."}, status_code=400)

    events = []

    async def capture_event(data: dict):
        # Keep this endpoint behavior aligned with the WebSocket route while
        # returning all intermediate tool events to the browser in one response.
        if isinstance(data, dict):
            events.append(data)

    try:
        await flora_agent.handle_message({"type": "message", "content": content, "mode": mode, "brief": brief}, capture_event)
    except Exception as exc:
        return JSONResponse({"ok": False, "error": str(exc)}, status_code=500)

    final_response = ""
    for event in reversed(events):
        if event.get("type") == "response":
            final_response = str(event.get("content") or "")
            break
        if event.get("type") == "error" and not final_response:
            final_response = str(event.get("content") or event.get("message") or "")

    return JSONResponse({
        "ok": True,
        "events": events,
        "response": final_response,
    })


@app.get("/api/flora/schedule")
async def flora_schedule_api(_user: str = Depends(require_auth)):
    """FLORA scheduled tasks for the dashboard schedule panel."""
    if not _FLORA_AVAILABLE:
        return JSONResponse([])
    try:
        return JSONResponse(flora_scheduler.list_tasks())
    except Exception as exc:
        return JSONResponse({"error": str(exc)}, status_code=500)

# ── Pump control ───────────────────────────────────────────────────────────────
@app.get("/api/plants")
async def list_plants(_user: str = Depends(require_auth)):
    return JSONResponse({
        "active": ACTIVE_PLANTS,
        "all": list(PLANTS),
        "names": PLANT_NAMES,
        "pumps": list(PUMP_PLANTS),
    })

# ── Dynamic moisture sensor add ───────────────────────────────────────────
# Lets the dashboard's `+ Add sensors` button discover & register new ADS1115
# channels on the fly. No restart — the new plant appears live on the grid.
_ALL_ADS_ADDRS = (0x48, 0x49, 0x4A, 0x4B)
_PLANT_LETTERS_MAX = list("abcdefghijklmnop")  # up to 16 plants (4 chips x 4 ch)

@app.get("/api/sensors/scan")
async def sensors_scan(_user: str = Depends(require_admin)):
    """Probe the I2C bus for ADS1115 channels and report which ones look
    plausible (a moisture sensor is wired and reading a sane value) and
    which are already mapped to a plant letter."""
    if not I2C_AVAILABLE:
        return JSONResponse({"ok": False, "error": "i2c_unavailable", "channels": []})
    taken = {(int(a), int(c)): p for p, (a, c) in SENSOR_CHANNELS.items()}
    out = []
    for addr in _ALL_ADS_ADDRS:
        for ch in range(4):
            try:
                _bus.write_i2c_block_data(addr, REG_CFG,
                    list(struct.pack(">H", MUX_CONFIGS[ch])))
                time.sleep(ADS_WAIT_S)
                raw = struct.unpack(">h",
                    bytes(_bus.read_i2c_block_data(addr, REG_CONV, 2)))[0]
                # Treat negative readings as missing sensor.
                if raw < 0:
                    raw = 0
                plausible = 3000 < raw < 22000
                out.append({
                    "addr": addr, "channel": ch, "raw": raw,
                    "plausible": bool(plausible),
                    "assigned_to": taken.get((addr, ch)),
                })
            except Exception as e:
                # Whole chip missing — record one entry per channel as unreadable.
                out.append({"addr": addr, "channel": ch, "error": str(e),
                            "assigned_to": taken.get((addr, ch))})
    unassigned = [c for c in out
                  if c.get("plausible") and c.get("assigned_to") is None]
    return JSONResponse({"ok": True, "channels": out, "unassigned": unassigned,
                         "i2c_available": True})

@app.post("/api/sensors/add")
async def sensors_add(request: Request, _user: str = Depends(require_admin)):
    """Add `count` moisture sensors. Scans the bus, picks unassigned
    plausible channels, and assigns each to the next free plant letter.
    Optional body field `relay_pins` (list[int]) wires up pumps too."""
    body = await request.json() if request.headers.get("content-type", "").startswith("application/json") else {}
    try:
        count = int(body.get("count", 1))
    except Exception:
        count = 1
    if count < 1 or count > 16:
        return JSONResponse({"ok": False, "error": "count must be 1..16"}, status_code=400)
    relay_pins = body.get("relay_pins") or []
    if not isinstance(relay_pins, list):
        relay_pins = []
    if not I2C_AVAILABLE:
        return JSONResponse({"ok": False, "error": "i2c_unavailable"}, status_code=409)
    # Find unassigned plausible channels.
    taken = {(int(a), int(c)) for (a, c) in SENSOR_CHANNELS.values()}
    candidates: list[tuple[int, int]] = []
    for addr in _ALL_ADS_ADDRS:
        for ch in range(4):
            if (addr, ch) in taken:
                continue
            try:
                _bus.write_i2c_block_data(addr, REG_CFG,
                    list(struct.pack(">H", MUX_CONFIGS[ch])))
                time.sleep(ADS_WAIT_S)
                raw = struct.unpack(">h",
                    bytes(_bus.read_i2c_block_data(addr, REG_CONV, 2)))[0]
                if raw < 0:
                    raw = 0
                if 3000 < raw < 22000:
                    candidates.append((addr, ch))
            except Exception:
                continue
            if len(candidates) >= count:
                break
        if len(candidates) >= count:
            break
    if len(candidates) < count:
        return JSONResponse({
            "ok": False,
            "error": f"only {len(candidates)} plausible sensor(s) detected — wire more in or check ADS1115 ADDR pin",
            "found": len(candidates),
        }, status_code=409)
    next_letters = [p for p in _PLANT_LETTERS_MAX if p not in PLANTS]
    if len(next_letters) < count:
        return JSONResponse({
            "ok": False,
            "error": "plant letter pool exhausted (max 16)",
        }, status_code=409)
    added = []
    for i in range(count):
        letter = next_letters[i]
        addr, ch = candidates[i]
        relay = relay_pins[i] if i < len(relay_pins) else None
        if _register_extra_plant(letter, addr, ch, relay_pin=relay):
            added.append({"plant": letter, "addr": addr, "channel": ch,
                          "relay_pin": relay})
    print(f"[PLANTS] added {len(added)} new sensor(s): "
          + ", ".join(f"{a['plant']}@0x{a['addr']:02X}#{a['channel']}" for a in added))
    return JSONResponse({"ok": True, "added": added,
                         "active": ACTIVE_PLANTS, "all": list(PLANTS)})

@app.post("/api/plants/{plant}/{action}")
async def set_plant_active(plant: str, action: str, _user: str = Depends(require_admin)):
    plant = plant.lower()
    if plant not in PLANTS or action not in ("enable", "disable"):
        return JSONResponse({"ok": False, "error": "invalid"}, status_code=400)
    if action == "enable" and plant not in ACTIVE_PLANTS:
        ACTIVE_PLANTS.append(plant)
        ACTIVE_PLANTS.sort()
    elif action == "disable" and plant in ACTIVE_PLANTS:
        ACTIVE_PLANTS.remove(plant)
        _stop_plant_pump(plant)
    _save_plant_registry()
    print(f"[PLANTS] {plant.upper()} {action}d -> active={ACTIVE_PLANTS}")
    return JSONResponse({"ok": True, "active": ACTIVE_PLANTS})

@app.post("/api/pump/{plant}/{action}")
async def pump_ctrl(plant: str, action: str, _user: str = Depends(require_admin)):
    plant = plant.lower()
    if plant not in PLANTS or action not in ("on", "off"):
        return JSONResponse({"ok": False, "error": "invalid"}, status_code=400)
    if plant not in PUMP_PLANTS:
        return JSONResponse({"ok": False, "error": "sensor_only",
                             "plant": plant, "message": "no relay configured for this sensor"}, status_code=409)
    on = action == "on"
    sensor_warning = None
    if on:
        with moisture_lock:
            mv = moisture_vals[plant]
        with sensor_lock:
            sensor_online = bool(sensor_status[plant].get("online"))
            sensor_error = sensor_status[plant].get("last_error")
        # Hardlock still blocks watering when a real online reading is too wet.
        if sensor_online and mv is not None and mv >= LOCK_PCT:
            return JSONResponse({"ok": False, "error": "locked",
                                 "moisture": mv, "lock_at": LOCK_PCT})
        if not sensor_online or mv is None:
            sensor_warning = sensor_error or "sensor_offline"
        # Start a commanded burst: sensor_irr_loop drives the identical
        # 3s-ON / 10s-soak cycle, stops at STOP_PCT, and is bounded by both
        # CMD_MAX_S and the LOCK_PCT hardlock. Admin override works even with
        # the sensor offline (blind, time-boxed).
        with pump_lock:
            burst_state[plant] = "idle"
            manual_pumps[plant] = True
        cmd_deadline[plant] = time.time() + CMD_MAX_S
    else:
        _stop_plant_pump(plant)
    print(f"[MANUAL] Plant {plant.upper()} burst {'REQUESTED' if on else 'STOPPED'}")
    payload = {"ok": True, "plant": plant, "on": on}
    if sensor_warning:
        payload.update({
            "warning": "sensor_offline_manual_override",
            "message": "Manual pump override allowed; moisture sensor is offline.",
            "sensor_error": sensor_warning,
        })
    return JSONResponse(payload)

# ── Auto irrigation toggle ─────────────────────────────────────────────────────
@app.post("/api/auto_irrigation")
async def set_auto(data: dict, _user: str = Depends(require_admin)):
    global auto_enabled
    with auto_lock:
        auto_enabled = bool(data.get("enabled", True))
    if not auto_enabled:
        for plant in PUMP_PLANTS:
            # Only auto bursts stop when AUTO is switched off; an explicit
            # commanded burst (manual button / FLORA) keeps running.
            if not manual_pumps[plant] and burst_state[plant] in ("burst_on", "burst_wait"):
                _stop_plant_pump(plant)
                print(f"[AUTO-OFF] Plant {plant.upper()} pump forced OFF")
    print(f"[AUTO] {'Enabled' if auto_enabled else 'Disabled'}")
    return JSONResponse({"ok": True, "enabled": auto_enabled})

# ── Guard / presence toggle ────────────────────────────────────────────────────
@app.post("/set_presence")
async def set_presence(data: dict, _user: str = Depends(require_admin)):
    global at_farm
    with at_farm_lock:
        at_farm = bool(data.get("at_farm", False))
    state = "AT FARM (guard OFF)" if at_farm else "AWAY (guard ON)"
    print(f"[GUARD] {state}")
    return JSONResponse({"ok": True, "at_farm": at_farm})

@app.post("/api/buzzer")
async def buzzer_mute(data: dict, _user: str = Depends(require_admin)):
    global siren_enabled
    siren_enabled = bool(data.get("enabled", True))
    if not siren_enabled:
        _set_siren(False)
    print(f"[BUZZER] siren {'enabled' if siren_enabled else 'muted'}")
    return JSONResponse({"ok": True, "enabled": siren_enabled, "available": BUZZER_AVAILABLE})

@app.post("/api/buzzer/test")
async def buzzer_test(_user: str = Depends(require_admin)):
    if not BUZZER_AVAILABLE:
        return JSONResponse({"ok": False, "error": "buzzers not connected"}, status_code=409)
    def _beep():
        for _ in range(3):
            _buzzer_tone(True); time.sleep(BUZZER_ON_S)
            _buzzer_tone(False); time.sleep(BUZZER_OFF_S)
    threading.Thread(target=_beep, daemon=True).start()
    return JSONResponse({"ok": True, "message": "test beep sent"})

@app.post("/api/camera/{camera}/{action}")
async def camera_ctrl(camera: str, action: str, _user: str = Depends(require_admin)):
    if action not in ("on", "off", "enable", "disable"):
        return JSONResponse({"ok": False, "error": "invalid"}, status_code=400)
    on = action in ("on", "enable")
    _flora_set_camera(camera, on)
    print(f"[CAMERA] {camera} monitoring {'ON' if on else 'OFF'}")
    return JSONResponse({"ok": True, "camera": camera.lower(), "on": on,
                         "security_cam_on": security_cam_on, "farm_cam_on": farm_cam_on})

# ── Alerts (compat) ────────────────────────────────────────────────────────────
@app.get("/alerts")
def alerts_api(_user: str = Depends(require_auth)):
    with at_farm_lock:
        af = at_farm
    return JSONResponse({"alerts": [a["name"] for a in active_alerts],
                         "at_farm": af, "detail": active_alerts})

# ── Full state snapshot ────────────────────────────────────────────────────────
@app.get("/api/state")
def state_api(_user: str = Depends(require_auth)):
    with moisture_lock:
        mv = dict(moisture_vals)
    with pump_lock:
        ps = dict(pump_states)
    with at_farm_lock:
        af = at_farm
    with auto_lock:
        ae = auto_enabled
    return JSONResponse({
        "type":     "state",
        "active_plants": ACTIVE_PLANTS,
        "all_plants":    list(PLANTS),
        "plant_names": PLANT_NAMES,
        "moisture": mv,
        "sensor_status": _sensor_snapshot(),
        "pumps":    ps,
        "auto_irr": ae,
        "at_farm":  af,
        "alerts":   active_alerts,
        "burst":    dict(burst_state),
        "last_watered": _last_watered_map(),
        "farm_monitor": _farm_status_snapshot(),
    })

# ── MJPEG stream ───────────────────────────────────────────────────────────────
@app.get("/stream")
def stream(_user: str = Depends(require_auth)):
    return StreamingResponse(_gen_frames(),
                             media_type="multipart/x-mixed-replace; boundary=frame")

@app.get("/farm_stream")
def farm_stream(_user: str = Depends(require_auth)):
    return StreamingResponse(_gen_farm_frames(),
                             media_type="multipart/x-mixed-replace; boundary=frame")

@app.get("/api/farm_monitor/status")
def farm_monitor_status(_user: str = Depends(require_auth)):
    return JSONResponse(_farm_status_snapshot())

@app.post("/api/farm_monitor/scan_now")
def farm_monitor_scan_now(_user: str = Depends(require_admin)):
    snap = _farm_status_snapshot()
    if snap.get("state") == "scanning":
        return JSONResponse({"ok": True, "message": "Farm Monitor scan already running", "status": snap})
    farm_scan_request.set()
    _farm_status_update(state="queued", message="Manual scan queued")
    return JSONResponse({"ok": True, "message": "Farm Monitor scan queued", "status": _farm_status_snapshot()})

# ── Storage API ────────────────────────────────────────────────────────────────
@app.get("/api/storage")
def storage_api(_user: str = Depends(require_auth)):
    return JSONResponse(_get_storage_tree())

# ── Storage image serving ──────────────────────────────────────────────────────
@app.get("/storage_img/{year}/{month}/{day}/{time_slot}/{filename}")
def serve_storage_img(year: str, month: str, day: str, time_slot: str, filename: str, _user: str = Depends(require_auth)):
    from fastapi.responses import FileResponse
    from fastapi import HTTPException
    safe_name = Path(filename).name
    folder = (STORAGE_PATH / year / month / day / time_slot).resolve()
    if not str(folder).startswith(str(STORAGE_PATH.resolve()) + os.sep):
        raise HTTPException(status_code=404)
    media_map = {".png": "image/png", ".jpg": "image/jpeg", ".jpeg": "image/jpeg"}
    if not _is_opaque_hashed_filename(safe_name):
        raise HTTPException(status_code=404, detail="Use hashed storage URL")
    img_path = _resolve_storage_image(folder, safe_name) if folder.exists() else None
    if img_path is None or img_path.suffix.lower() not in media_map:
        raise HTTPException(status_code=404, detail="Image not found")
    return FileResponse(str(img_path), media_type=media_map[img_path.suffix.lower()], headers={"Cache-Control": "public, max-age=31536000, immutable"})

# ── Analytics API ──────────────────────────────────────────────────────────────
@app.get("/api/analytics")
def analytics_api(_user: str = Depends(require_auth)):
    cutoff = time.time() - 86400
    with _hist_lock:
        mh = {k: [{"t": int(e["t"]), "v": e["v"]}
                  for e in moisture_hist[k][-288:]]
              for k in PLANTS}
        hourly = {str(h): 0 for h in range(24)}
        for d in detect_hist:
            if d["t"] >= cutoff and d.get("event_type") != "clear" and d.get("label") != "No Sustained Event":
                hr = str(datetime.fromtimestamp(d["t"]).hour)
                hourly[hr] = hourly.get(hr, 0) + 1
        species: dict = {}
        for d in detect_hist:
            if d["t"] >= cutoff and d.get("event_type") != "clear" and d.get("label") != "No Sustained Event":
                species[d["label"]] = species.get(d["label"], 0) + 1
        irr = [{"t": int(e["t"]), "plant": e["plant"]} for e in irr_hist[-100:]]
    with moisture_lock:
        cur = dict(moisture_vals)
    storage_summary = {"security": 0, "disease": 0, "ripeness": 0, "disease_and_ripeness": 0, "unknown": 0}
    latest_farm_event = None
    try:
        today_root = STORAGE_PATH / datetime.now().strftime("%Y") / datetime.now().strftime("%m") / datetime.now().strftime("%d")
        if today_root.exists():
            for meta_path in sorted(today_root.glob("*/meta.json")):
                try:
                    meta = json.loads(meta_path.read_text(encoding="utf-8"))
                except Exception:
                    continue
                kind = meta.get("event_type") or ("security" if str(meta.get("label", "")).lower() == "person" else "unknown")
                storage_summary[kind] = storage_summary.get(kind, 0) + 1
                if kind in ("disease", "ripeness", "disease_and_ripeness"):
                    latest_farm_event = meta
    except Exception as _e:
        hailo_logger.warning(f"analytics storage scan failed: {_e}")
    return JSONResponse({
        "moisture_history": mh,
        "moisture_current": cur,
        "sensor_status": _sensor_snapshot(),
        "hourly_detections": hourly,
        "species_counts": species,
        "irr_history": irr,
        "storage_summary": storage_summary,
        "latest_farm_event": latest_farm_event,
    })

# ── Serve static images (farmer.png, low-cortisol.png, etc.) ──────────────────
@app.get("/img/{filename}")
async def serve_image(filename: str):
    """Serve public static assets through opaque hash-only URLs.

    Login must load the favicon before a session exists, so this route is public.
    Direct named files are still blocked and event storage images remain authenticated.
    """
    from fastapi.responses import FileResponse
    from fastapi import HTTPException
    safe_name = Path(filename).name
    if not _is_opaque_hashed_filename(safe_name):
        raise HTTPException(status_code=404, detail="Use hashed asset URL")
    img_path = _resolve_opaque_asset(safe_name)
    if img_path is None:
        raise HTTPException(status_code=404, detail="Asset not found")
    return FileResponse(str(img_path), media_type=_ASSET_MEDIA[img_path.suffix.lower()], headers={"Cache-Control": "public, max-age=31536000, immutable"})

# ── Serve dashboard HTML ───────────────────────────────────────────────────────
SENSOR_UI_PATCH = r"""
<script>
(function(){
  function currentState(){
    try{ if(typeof state!=='undefined')return state||{}; }catch(_){}
    return window.state || {};
  }
  function sensorOnline(p){
    const s=currentState();
    const st=s.sensor_status&&s.sensor_status[p];
    const v=s.moisture&&s.moisture[p];
    return !!(st&&st.online===true&&v!==null&&v!==undefined);
  }
  function sensorHealthTag(){
    const heads=document.querySelectorAll('.card-head');
    for(const head of heads){
      const title=head.querySelector('.card-title');
      if(title&&title.textContent.trim()==='Sensor Health')return head.querySelector('.tag');
    }
    return null;
  }
  function applySensorUi(){
    const s=currentState();
    if(!s.moisture)return;
    const plants=['a','b','c','d','e','f','g','h'];
    const online=plants.filter(sensorOnline).length;
    const quick=document.querySelector('.quick-tiles .qtile:nth-child(3) .qtile-val');
    if(quick){
      quick.textContent=online+'/8';
      quick.className='qtile-val '+(online===8?'safe':online>0?'warn':'danger');
    }
    const quickLbl=document.querySelector('.quick-tiles .qtile:nth-child(3) .qtile-lbl');
    if(quickLbl)quickLbl.textContent=online===8?'Sensors OK':(online===0?'Sensors Offline':'Sensors Partial');
    document.querySelectorAll('.auto-info-row').forEach(row=>{
      const lbl=row.querySelector('.lbl');
      const val=row.querySelector('.val');
      if(lbl&&val&&lbl.textContent.trim()==='Stop target')val.textContent='>= 60%';
    });
    const tag=sensorHealthTag();
    if(tag){
      tag.textContent=online===8?'All Active':(online===0?'Offline':'Partial');
      tag.className=online===8?'tag tag-teal':(online===0?'tag tag-alert':'tag tag-warn');
    }
    const chips=document.querySelectorAll('.sensor-grid .sensor-chip');
    plants.forEach((p,i)=>{
      const isOn=sensorOnline(p);
      const chip=chips[i];
      if(chip){
        chip.style.opacity='1';
        chip.style.borderColor=isOn?'':'#fca5a5';
        chip.style.background=isOn?'':'#fef2f2';
        const dot=chip.querySelector('.sc-dot');
        const txt=chip.querySelector('.sc-ok');
        if(dot){
          dot.style.background=isOn?'':'#ef4444';
          dot.style.boxShadow=isOn?'':'0 0 0 4px rgba(239,68,68,.18)';
          dot.style.animation=isOn?'':'ablink .8s infinite';
        }
        if(txt){
          txt.textContent=isOn?'OK':'OFFLINE';
          txt.style.color=isOn?'':'#b91c1c';
          txt.style.fontWeight=isOn?'':'800';
        }
      }
      if(!isOn){
        const card=document.getElementById('pc-'+p);
        const val=document.getElementById('pv-'+p);
        const badge=document.getElementById('pb-'+p);
        const btn=document.getElementById('btn-'+p);
        if(card)card.className='plant-card c-crit';
        if(val)val.textContent='OFF';
        if(badge){badge.textContent='Sensor Offline';badge.className='pc-badge tag tag-alert';}
        if(btn && btn.dataset.pumpOn!=='true'){
          btn.className='btn-water on';
          btn.disabled=false;
          btn.textContent='💧 Water '+p.toUpperCase();
          btn.dataset.pumpOn='false';
          btn.style.color='';
          btn.title='Sensor offline: admin manual override available';
          // The original dashboard.html renders btn-e..btn-h with no onclick
          // (just <button ... disabled>Sensor Only</button>) so clicks did
          // nothing even after we unlocked them. Wire the handler now.
          if(!btn.onclick && typeof window.manualPump==='function'){
            btn.onclick=function(){window.manualPump(p);};
          }
        }
        const row=document.getElementById('ov-'+p);
        if(row){
          const pct=row.querySelector('.ov-pct');
          const dot=row.querySelector('.ov-dot');
          const lbl=row.querySelector('.ov-slbl');
          if(pct){pct.textContent='OFF';pct.style.color='#b91c1c';}
          if(dot){dot.style.background='#ef4444';dot.style.animation='ablink .8s infinite';}
          if(lbl){lbl.textContent='Offline';lbl.style.color='#b91c1c';lbl.style.fontWeight='800';}
        }
      }
    });
  }
  const oldHandle=window.handleState;
  if(typeof oldHandle==='function'&&!oldHandle.__sensorPatch){
    const wrapped=function(d){ oldHandle(d); applySensorUi(); };
    wrapped.__sensorPatch=true;
    window.handleState=wrapped;
  }
  const oldBars=window.drawBarsChart;
  if(typeof oldBars==='function'&&!oldBars.__sensorPatch){
    window.drawBarsChart=function(data){
      const ctx=getCtx('chart-bars'); if(!ctx)return;
      const W=ctx._w,H=ctx._h,plants=['a','b','c','d','e','f','g','h'],labels=['Plant A','Plant B','Plant C','Plant D','Plant E','Plant F','Plant G','Plant H'];
      ctx.clearRect(0,0,W,H);
      const pad=30,bw=(W-pad*2)/plants.length,maxH=H-50;
      ctx.fillStyle='rgba(13,138,120,.07)';ctx.fillRect(pad,H-maxH*(75/100)-20,W-pad*2,maxH*(20/100));
      for(let i=0;i<plants.length;i++){
        const p=plants[i],v=data?data[p]:null,isOn=v!==null&&v!==undefined;
        const safeV=isOn?Math.max(0,Math.min(100,v)):0;
        const col=!isOn?'#94a3b8':safeV<40?'#ef4444':safeV<60?'#f59e0b':safeV<=80?'#13b3a0':'#0ea5e9';
        const bh=(safeV/100)*maxH,x=pad+i*bw+bw*.15,bw2=bw*.7;
        const g=ctx.createLinearGradient(0,H-20-bh,0,H-20);g.addColorStop(0,col);g.addColorStop(1,col+'80');
        ctx.fillStyle=g;ctx.beginPath();ctx.roundRect?ctx.roundRect(x,H-20-bh,bw2,Math.max(2,bh),[6,6,0,0]):ctx.rect(x,H-20-bh,bw2,Math.max(2,bh));ctx.fill();
        ctx.fillStyle=col;ctx.font='bold 11px JetBrains Mono, monospace';ctx.textAlign='center';ctx.fillText(isOn?Math.round(safeV)+'%':'OFF',x+bw2/2,H-20-bh-6);
        ctx.fillStyle='rgba(107,140,158,.8)';ctx.font='11px Plus Jakarta Sans, sans-serif';ctx.fillText(labels[i],x+bw2/2,H-4);
      }
      ctx.strokeStyle='rgba(210,232,237,.6)';ctx.lineWidth=1;ctx.beginPath();ctx.moveTo(pad,H-20);ctx.lineTo(W-pad,H-20);ctx.stroke();
    };
    window.drawBarsChart.__sensorPatch=true;
  }
  setInterval(applySensorUi,1000);
})();
</script>
<script>
/* +Add sensors button + dynamic plant cards (letters i..p) — injected here so
   dashboard.html stays byte-for-byte identical to the original. The original
   theme, layout, colours, and CSS are NOT modified; we only add an admin-only
   button to the .avg-strip and the JS that grows the .plant-grid when the user
   adds more sensors at runtime. */
(function(){
  function isViewer(){ try{ return typeof currentUser!=='undefined' && currentUser && currentUser.role==='viewer'; }catch(_){ return false; } }
  function ensureAddBtn(){
    if(document.getElementById('btn-add-sensor'))return;
    const strip=document.querySelector('.avg-strip .avg-right');
    if(!strip)return;
    const btn=document.createElement('button');
    btn.id='btn-add-sensor';
    btn.type='button';
    btn.setAttribute('data-admin','');
    btn.title='Scan the I2C bus for new ADS1115 channels and add the matching moisture bar';
    btn.style.cssText='border:1px solid var(--border);background:linear-gradient(135deg,var(--teal-lt),#fff);color:var(--teal-dk);font-weight:800;font-size:.66rem;letter-spacing:.06em;text-transform:uppercase;padding:8px 12px;border-radius:999px;cursor:pointer;box-shadow:0 4px 12px rgba(13,138,120,.12);white-space:nowrap;margin-left:10px';
    btn.innerHTML='<span style="font-size:.95rem;font-weight:900;margin-right:4px">＋</span>Add sensors';
    btn.addEventListener('click',addSensors);
    btn.style.display=isViewer()?'none':'inline-flex';
    strip.appendChild(btn);
  }
  function _plantUniverse(){
    try{ return (window.state&&state.all_plants&&state.all_plants.length)?state.all_plants:'abcdefghijklmnop'.split(''); }
    catch(_){ return 'abcdefghijklmnop'.split(''); }
  }
  function _ensurePlantCard(p){
    if(document.getElementById('pc-'+p))return;
    const grid=document.querySelector('.plant-grid');
    if(!grid)return;
    const U=p.toUpperCase();
    const card=document.createElement('div');
    card.className='plant-card c-good';
    card.id='pc-'+p;
    card.innerHTML=
      '<div class="pc-name">Plant '+U+'</div>'+
      '<div class="gauge-wrap"><svg class="gauge-svg" viewBox="0 0 120 120">'+
        '<path fill="none" stroke="#ddeef2" stroke-width="12" stroke-linecap="round" d="M60 8 A52 52 0 1 1 60 112 A52 52 0 1 1 60 8"/>'+
        '<path class="g-fill" id="gf-'+p+'" d="M60 8 A52 52 0 1 1 60 112 A52 52 0 1 1 60 8" stroke-dasharray="326.7" stroke-dashoffset="326.7"/>'+
        '<text class="g-val" id="pv-'+p+'" x="60" y="62">--</text>'+
      '</svg></div>'+
      '<div class="pc-badge bg-good" id="pb-'+p+'">—</div>'+
      '<div class="pc-div"></div>'+
      '<button class="btn-water locked" id="btn-'+p+'" disabled>Sensor Only</button>';
    grid.appendChild(card);
    // Wire the click handler so admin manual override works as soon as the
    // sensor goes offline (matches the SENSOR_UI_PATCH offline-unlock branch).
    const _b=card.querySelector('#btn-'+p);
    if(_b)_b.onclick=function(){window.manualPump&&window.manualPump(p);};
  }
  function applyExtraPlantVisibility(){
    let act=[];
    try{ act=(typeof activePlants==='function')?activePlants():[]; }catch(_){}
    for(const p of _plantUniverse()){
      if(act.indexOf(p)>=0)_ensurePlantCard(p);
      const c=document.getElementById('pc-'+p);
      if(c)c.style.display=act.indexOf(p)>=0?'':'none';
    }
  }
  window.addSensors=async function(){
    if(typeof requireAdminControl==='function' && !requireAdminControl('Add sensors'))return;
    const ansN=prompt('How many new moisture sensors do you want to add?\n\n(They will appear on the dashboard as soon as I find them on the I²C bus.)','1');
    if(ansN===null)return;
    const count=parseInt(ansN,10);
    if(!(count>=1 && count<=16)){alert('Please enter a number from 1 to 16.');return;}
    const ansP=prompt('Optional — BCM pins for the new pumps (comma-separated, blank = sensor-only).\n\nExample: 4,25',' ');
    let relay_pins=[];
    if(ansP!==null){
      relay_pins=ansP.split(',').map(s=>parseInt(s.trim(),10)).filter(n=>Number.isInteger(n)&&n>=0&&n<28);
    }
    try{
      const r=await fetch('/api/sensors/add',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({count,relay_pins})});
      const data=await r.json();
      if(!r.ok||!data.ok){alert('Could not add sensors: '+(data.error||r.statusText));return;}
      const added=(data.added||[]).map(a=>'• Plant '+a.plant.toUpperCase()+' @ 0x'+a.addr.toString(16).toUpperCase()+' ch'+a.channel+(a.relay_pin!=null?' (pump pin '+a.relay_pin+')':' (sensor-only)')).join('\n');
      alert('Added '+(data.added||[]).length+' sensor(s):\n\n'+added+'\n\nThey will appear on the dashboard within a few seconds.');
      if(typeof refresh==='function')refresh();
    }catch(e){alert('Add sensors failed: '+e);}
  };
  function applyAddBtnVisibility(){
    const b=document.getElementById('btn-add-sensor');
    if(b)b.style.display=isViewer()?'none':'inline-flex';
  }
  // Ensure every plant water button has its click handler wired. The original
  // dashboard.html ships btn-e..btn-h as `<button ... disabled>Sensor Only</button>`
  // with NO onclick, so even after the SENSOR_UI_PATCH unlocks them clicks
  // silently did nothing. This restores click-to-water for all plants.
  function ensurePumpHandlers(){
    if(typeof window.manualPump!=='function')return;
    for(const p of _plantUniverse()){
      const btn=document.getElementById('btn-'+p);
      if(btn && !btn.onclick) btn.onclick=function(){window.manualPump(p);};
    }
  }
  // Friendlier toast for the 409 "sensor_only" response so the user knows
  // the relay simply isn't wired up for this plant (vs. a generic error).
  (function wrapManualPump(){
    const orig=window.manualPump;
    if(typeof orig!=='function' || orig.__sensorOnlyPatch) return;
    const wrapped=async function(p){
      const _toast=window.showToast||function(){};
      const origFetch=window.fetch;
      window.fetch=async function(u,o){
        const r=await origFetch(u,o);
        if(typeof u==='string' && u.indexOf('/api/pump/')===0 && r.status===409){
          try{
            const data=await r.clone().json();
            if(data && data.error==='sensor_only'){
              _toast('🔧 Plant '+p.toUpperCase()+' has no pump wired up — sensor-only plant');
            }
          }catch(_){}
        }
        return r;
      };
      try{ return await orig(p); }
      finally{ window.fetch=origFetch; }
    };
    wrapped.__sensorOnlyPatch=true;
    window.manualPump=wrapped;
  })();
  // Wait for the DOM to settle, then inject the button and start the
  // dynamic-plant-card maintainer.
  function start(){
    ensureAddBtn();
    applyExtraPlantVisibility();
    applyAddBtnVisibility();
    ensurePumpHandlers();
    setInterval(function(){
      ensureAddBtn();
      applyExtraPlantVisibility();
      applyAddBtnVisibility();
      ensurePumpHandlers();
    },1500);
  }
  if(document.readyState==='complete'||document.readyState==='interactive'){
    setTimeout(start,80);
  }else{
    document.addEventListener('DOMContentLoaded',start);
  }
})();
</script>
"""

def _inject_sensor_ui_patch(html: str) -> str:
    if "sensor_status" in html and "__sensorPatch" in html:
        return html
    if "</body>" in html:
        return html.replace("</body>", SENSOR_UI_PATCH + "</body>")
    return html + SENSOR_UI_PATCH

FARM_MONITOR_UI_PATCH = r"""
<style>
.farm-scan-btn{border:0;border-radius:999px;padding:10px 15px;font-weight:800;letter-spacing:.2px;background:linear-gradient(135deg,var(--teal),#4ee0be);color:#fff;box-shadow:0 10px 24px rgba(13,138,120,.18);cursor:pointer;transition:transform .18s,opacity .18s}
.farm-scan-btn:hover{transform:translateY(-1px)}
.farm-scan-btn:disabled{opacity:.55;cursor:wait;transform:none}
.farm-scan-grid{display:grid;grid-template-columns:repeat(3,1fr);gap:10px;padding:14px 16px}
.farm-scan-stat{background:var(--bg);border:1px solid var(--border);border-radius:12px;padding:12px}
.farm-scan-k{font-size:.62rem;text-transform:uppercase;letter-spacing:1.1px;color:var(--muted);font-weight:800}
.farm-scan-v{font-family:'JetBrains Mono',monospace;font-size:1rem;font-weight:800;margin-top:4px;color:var(--teal-dk)}
.farm-scan-note{padding:0 16px 14px;color:var(--muted);font-size:.78rem;line-height:1.6}
.farm-scan-progress{margin:0 16px 14px;padding:14px;border:1px solid var(--border);border-radius:16px;background:linear-gradient(180deg,#fbfffd,#eef8f6)}
.farm-scan-progress-top{display:flex;align-items:center;justify-content:space-between;gap:12px;font-size:.76rem;color:var(--muted);font-weight:800;text-transform:uppercase;letter-spacing:.8px}
.farm-scan-progress-track{height:10px;border-radius:999px;background:#dcebec;overflow:hidden;margin-top:10px}
.farm-scan-progress-bar{display:block;height:100%;width:0%;border-radius:999px;background:linear-gradient(90deg,var(--teal),#4ee0be);transition:width .35s ease}
.farm-scan-steps{display:grid;grid-template-columns:repeat(4,minmax(0,1fr));gap:9px;margin:0 16px 14px}
.farm-scan-step{border:1px solid var(--border);border-radius:14px;background:var(--bg);padding:11px;min-width:0}
.farm-scan-step b{display:block;font-size:.76rem;color:var(--ink)}
.farm-scan-step small{display:block;color:var(--muted);font-size:.65rem;margin-top:4px;line-height:1.35}
.farm-scan-step.active{border-color:#7dd3c7;background:#f0fffb;box-shadow:0 8px 18px rgba(13,138,120,.08)}
.farm-scan-step.done{border-color:#b8efe7;background:#f7fffd}
.farm-scan-step.warn{border-color:#fcd34d;background:#fffbeb}
.farm-scan-findings{display:grid;grid-template-columns:1fr 1fr;gap:10px;margin:0 16px 16px}
.farm-finding{border:1px solid var(--border);border-radius:14px;background:var(--bg);padding:12px}
.farm-finding strong{display:block;font-size:.78rem;color:var(--ink)}
.farm-finding span{display:block;font-family:'JetBrains Mono',monospace;font-weight:900;color:var(--teal-dk);margin-top:6px}
.farm-finding small{display:block;color:var(--muted);font-size:.66rem;margin-top:5px;line-height:1.35}
#farm-scan-card{overflow:hidden;background:linear-gradient(180deg,#ffffff,#f7fcfb)}
#farm-scan-card .card-head{background:linear-gradient(90deg,#ffffff,#effaf8)}
#farm-scan-tag.tag-warn:before{content:'';display:inline-block;width:8px;height:8px;border-radius:999px;background:#d97706;margin-right:6px;box-shadow:0 0 0 0 rgba(217,119,6,.55);animation:farmPulse 1.15s infinite}
@keyframes farmPulse{70%{box-shadow:0 0 0 9px rgba(217,119,6,0)}100%{box-shadow:0 0 0 0 rgba(217,119,6,0)}}
.farm-scan-progress{background:linear-gradient(135deg,#ecfffb,#f7fffd);box-shadow:inset 0 1px 0 rgba(255,255,255,.8)}
.farm-scan-steps{grid-template-columns:repeat(4,minmax(120px,1fr));align-items:stretch}
.farm-scan-step{position:relative;overflow:hidden}
.farm-scan-step.active:after{content:'';position:absolute;left:0;right:0;bottom:0;height:3px;background:linear-gradient(90deg,var(--teal),#4ee0be);animation:farmSlide 1.1s ease-in-out infinite}
@keyframes farmSlide{0%{transform:translateX(-100%)}100%{transform:translateX(100%)}}
.farm-scan-step b{white-space:nowrap;overflow:hidden;text-overflow:ellipsis}
.farm-scan-step small{display:-webkit-box;-webkit-line-clamp:2;-webkit-box-orient:vertical;overflow:hidden;min-height:2.7em}
.farm-scan-note{border-top:1px solid var(--border);margin:0 16px;padding:12px 0 14px}
@media(max-width:720px){.farm-scan-grid,.farm-scan-steps,.farm-scan-findings{grid-template-columns:1fr}.farm-scan-btn{width:100%;margin-top:8px}.guard-strip{align-items:flex-start;gap:10px;flex-wrap:wrap}}
</style>
<script>
(function(){
  window.__farmMonitorPatch=true;
  function fmtTime(iso){if(!iso)return'—';try{return new Date(iso).toLocaleString();}catch(_){return'—';}}
  function ensureFarmMonitorUi(){
    const img=document.getElementById('farm-live-feed');
    if(img&&img.getAttribute('src')!=='/farm_stream')img.setAttribute('src','/farm_stream');
    const toggle=document.getElementById('farm-monitor-toggle');
    const strip=toggle?toggle.closest('.guard-strip'):null;
    if(strip&&!document.getElementById('farm-scan-now')){
      const btn=document.createElement('button');
      btn.id='farm-scan-now';btn.className='farm-scan-btn';btn.type='button';btn.textContent='Scan Now';
      btn.onclick=window.scanFarmNow;
      strip.appendChild(btn);
    }
    const chips=document.getElementById('farm-det-chips');
    if(chips&&!document.getElementById('farm-scan-card')){
      chips.closest('.card').insertAdjacentHTML('beforebegin',`
        <div class="card" id="farm-scan-card">
          <div class="card-head"><span class="card-title">Farm Monitor Scan</span><span class="tag tag-grey" id="farm-scan-tag">Waiting</span></div>
          <div class="farm-scan-grid">
            <div class="farm-scan-stat"><div class="farm-scan-k">Next Scan</div><div class="farm-scan-v" id="farm-scan-next">—</div></div>
            <div class="farm-scan-stat"><div class="farm-scan-k">Plant Health</div><div class="farm-scan-v" id="farm-scan-disease">—</div></div>
            <div class="farm-scan-stat"><div class="farm-scan-k">Harvest Signal</div><div class="farm-scan-v" id="farm-scan-ripe">—</div></div>
          </div>
          <div class="farm-scan-progress">
            <div class="farm-scan-progress-top"><span id="farm-scan-stage">Waiting</span><span id="farm-scan-count">0/25 frames</span></div>
            <div class="farm-scan-progress-track"><span class="farm-scan-progress-bar" id="farm-scan-progress-bar"></span></div>
          </div>
          <div class="farm-scan-steps">
            <div class="farm-scan-step" data-farm-step="capture"><b>1. Capture frames</b><small id="farm-step-capture">Waiting for Scan Now.</small></div>
            <div class="farm-scan-step" data-farm-step="disease"><b>2. Plant Health</b><small id="farm-step-disease">Disease model ready.</small></div>
            <div class="farm-scan-step" data-farm-step="ripeness"><b>3. Harvest Signal</b><small id="farm-step-ripeness">Ripeness model ready.</small></div>
            <div class="farm-scan-step" data-farm-step="decision"><b>4. Decision</b><small id="farm-step-decision">Waiting for results.</small></div>
          </div>
          <div class="farm-scan-findings">
            <div class="farm-finding"><strong>Health warning frames</strong><span id="farm-find-disease">0 / 0</span><small>Disease or plant-health signs found by the health model.</small></div>
            <div class="farm-finding"><strong>Harvest signal frames</strong><span id="farm-find-ripe">0 / 0</span><small>Ripe, nearly ripe, or flowering signs found by the harvest model.</small></div>
          </div>
          <div class="farm-scan-note" id="farm-scan-message">Scheduled 6-hour scanning is ready.</div>
        </div>`);
    }
  }
  function applyFarmStatus(s){
    ensureFarmMonitorUi();
    const tag=document.getElementById('farm-scan-tag');
    const msg=document.getElementById('farm-scan-message');
    const next=document.getElementById('farm-scan-next');
    const dis=document.getElementById('farm-scan-disease');
    const ripe=document.getElementById('farm-scan-ripe');
    const btn=document.getElementById('farm-scan-now');
    const label=document.getElementById('guard-label');
    const sub=document.getElementById('guard-sub');
    const result=s&&s.last_result?s.last_result:null;
    if(tag){tag.textContent=(s&&s.state?s.state:'waiting').toUpperCase();tag.className=s&&s.state==='scanning'?'tag tag-warn':(s&&s.state==='error'?'tag tag-alert':'tag tag-teal');}
    if(msg)msg.textContent=(s&&s.message)||'Scheduled 6-hour scanning is ready.';
    if(next)next.textContent=fmtTime(s&&s.next_scan_at);
    if(dis)dis.textContent=result?Math.round((result.disease_ratio||0)*100)+'%':'—';
    if(ripe)ripe.textContent=result?Math.round((result.ripeness_ratio||0)*100)+'%':'—';
    if(btn)btn.disabled=!!(s&&s.state==='scanning');
    if(label)label.textContent='Farm Monitor';
    if(sub)sub.textContent=s&&s.state==='scanning'?'Scanning frames with plant health models':((s&&s.message)||'Health monitoring can run on captured farm frames');
    if(typeof farmSetProgress==='function')farmSetProgress(s||{});
  }
  window.loadFarmMonitorStatus=async function(){
    try{const r=await fetch('/api/farm_monitor/status');if(!r.ok)return;applyFarmStatus(await r.json());}
    catch(_){}
  };
  window.scanFarmNow=async function(){
    ensureFarmMonitorUi();
    const btn=document.getElementById('farm-scan-now');
    if(btn){btn.disabled=true;btn.textContent='Queued...';}
    try{
      const r=await fetch('/api/farm_monitor/scan_now',{method:'POST'});
      const d=await r.json();
      if(window.showToast)showToast(d.message||'Farm Monitor scan queued');
      if(d.status)applyFarmStatus(d.status);
    }catch(_){if(window.showToast)showToast('Farm Monitor scan request failed');}
    finally{if(btn){btn.textContent='Scan Now';setTimeout(()=>window.loadFarmMonitorStatus&&window.loadFarmMonitorStatus(),1200);}}
  };
  const oldHandle=window.handleState;
  if(typeof oldHandle==='function'&&!oldHandle.__farmMonitorPatch){
    const wrapped=function(d){oldHandle(d);if(d&&d.farm_monitor)applyFarmStatus(d.farm_monitor);};
    wrapped.__farmMonitorPatch=true;window.handleState=wrapped;
  }
  document.addEventListener('DOMContentLoaded',()=>{ensureFarmMonitorUi();window.loadFarmMonitorStatus();});
  setInterval(()=>window.loadFarmMonitorStatus&&window.loadFarmMonitorStatus(),5000);
})();
</script>
"""

DASHBOARD_INTEGRATION_PATCH = r"""
<style>
.farm-event-list{display:grid;gap:12px;padding:14px 16px}
.farm-scan-btn{border:0;border-radius:999px;padding:10px 15px;font-weight:800;letter-spacing:.2px;background:linear-gradient(135deg,var(--teal),#4ee0be);color:#fff;box-shadow:0 10px 24px rgba(13,138,120,.18);cursor:pointer;transition:transform .18s,opacity .18s}
.farm-scan-btn:hover{transform:translateY(-1px)}
.farm-scan-btn:disabled{opacity:.55;cursor:wait;transform:none}
.farm-scan-grid{display:grid;grid-template-columns:repeat(3,1fr);gap:10px;padding:14px 16px}
.farm-scan-stat{background:var(--bg);border:1px solid var(--border);border-radius:12px;padding:12px}
.farm-scan-k{font-size:.62rem;text-transform:uppercase;letter-spacing:1.1px;color:var(--muted);font-weight:800}
.farm-scan-v{font-family:'JetBrains Mono',monospace;font-size:1rem;font-weight:800;margin-top:4px;color:var(--teal-dk)}
.farm-scan-note{padding:0 16px 14px;color:var(--muted);font-size:.78rem;line-height:1.6}
.farm-event-card{display:flex;gap:12px;align-items:flex-start;border:1px solid var(--border);border-radius:14px;padding:14px;background:var(--bg)}
.farm-event-card.good{background:linear-gradient(135deg,#ecfdf5,#f6fffb);border-color:#a7f3d0}
.farm-event-card.warn{background:linear-gradient(135deg,#fff7ed,#fffaf0);border-color:#fcd34d}
.farm-event-card.danger{background:linear-gradient(135deg,#fef2f2,#fff7f7);border-color:#fca5a5}
.farm-event-mark{width:36px;height:36px;border-radius:12px;display:grid;place-items:center;font-weight:900;flex:0 0 auto}
.farm-event-card.good .farm-event-mark{background:#d1fae5;color:#047857}
.farm-event-card.warn .farm-event-mark{background:#fef3c7;color:#b45309}
.farm-event-card.danger .farm-event-mark{background:#fee2e2;color:#b91c1c}
.farm-event-title{font-weight:800;font-size:.9rem}
.farm-event-text{color:var(--muted);font-size:.78rem;line-height:1.55;margin-top:4px}
.farm-scan-progress{margin:0 16px 14px;padding:14px;border:1px solid var(--border);border-radius:16px;background:linear-gradient(135deg,#ecfffb,#f7fffd);box-shadow:inset 0 1px 0 rgba(255,255,255,.8)}
.farm-scan-progress-top{display:flex;align-items:center;justify-content:space-between;gap:12px;font-size:.76rem;color:var(--muted);font-weight:800;text-transform:uppercase;letter-spacing:.8px}
.farm-scan-progress-track{height:10px;border-radius:999px;background:#dcebec;overflow:hidden;margin-top:10px}
.farm-scan-progress-bar{display:block;height:100%;width:0%;border-radius:999px;background:linear-gradient(90deg,var(--teal),#4ee0be);transition:width .35s ease}
.farm-scan-steps{display:grid;grid-template-columns:repeat(4,minmax(120px,1fr));gap:9px;margin:0 16px 14px;align-items:stretch}
.farm-scan-step{position:relative;overflow:hidden;border:1px solid var(--border);border-radius:14px;background:var(--bg);padding:11px;min-width:0}
.farm-scan-step b{display:block;font-size:.76rem;color:var(--ink);white-space:nowrap;overflow:hidden;text-overflow:ellipsis}
.farm-scan-step small{display:-webkit-box;-webkit-line-clamp:2;-webkit-box-orient:vertical;overflow:hidden;min-height:2.7em;color:var(--muted);font-size:.65rem;margin-top:4px;line-height:1.35}
.farm-scan-step.active{border-color:#7dd3c7;background:#f0fffb;box-shadow:0 8px 18px rgba(13,138,120,.08)}
.farm-scan-step.done{border-color:#b8efe7;background:#f7fffd}
.farm-scan-step.warn{border-color:#fcd34d;background:#fffbeb}
.farm-scan-step.active:after{content:'';position:absolute;left:0;right:0;bottom:0;height:3px;background:linear-gradient(90deg,var(--teal),#4ee0be);animation:farmSlide 1.1s ease-in-out infinite}
@keyframes farmSlide{0%{transform:translateX(-100%)}100%{transform:translateX(100%)}}
.farm-scan-findings{display:grid;grid-template-columns:1fr 1fr;gap:10px;margin:0 16px 16px}
.farm-finding{border:1px solid var(--border);border-radius:14px;background:var(--bg);padding:12px}
.farm-finding strong{display:block;font-size:.78rem;color:var(--ink)}
.farm-finding span{display:block;font-family:'JetBrains Mono',monospace;font-weight:900;color:var(--teal-dk);margin-top:6px}
.farm-finding small{display:block;color:var(--muted);font-size:.66rem;margin-top:5px;line-height:1.35}
#farm-scan-card{overflow:hidden;background:linear-gradient(180deg,#ffffff,#f7fcfb)}
#farm-scan-card .card-head{background:linear-gradient(90deg,#ffffff,#effaf8)}
#farm-scan-tag.tag-warn:before{content:'';display:inline-block;width:8px;height:8px;border-radius:999px;background:#d97706;margin-right:6px;box-shadow:0 0 0 0 rgba(217,119,6,.55);animation:farmPulse 1.15s infinite}
@keyframes farmPulse{70%{box-shadow:0 0 0 9px rgba(217,119,6,0)}100%{box-shadow:0 0 0 0 rgba(217,119,6,0)}}
.farm-scan-note{border-top:1px solid var(--border);margin:0 16px;padding:12px 0 14px}
.analytics-modern{display:grid;gap:16px}
.analytics-hero{display:grid;grid-template-columns:repeat(3,minmax(0,1fr));gap:12px}
.analytics-tile{background:var(--card);border:1px solid var(--border);border-radius:16px;padding:18px;box-shadow:var(--shadow)}
.analytics-k{font-size:.68rem;text-transform:uppercase;letter-spacing:1.4px;color:var(--muted);font-weight:800}
.analytics-v{font-family:'JetBrains Mono',monospace;font-weight:900;font-size:1.35rem;margin-top:8px;color:var(--teal-dk)}
.analytics-note{font-size:.78rem;line-height:1.6;color:var(--muted);margin-top:7px}
.analytics-list{display:grid;gap:8px}
.analytics-row{display:flex;align-items:center;justify-content:space-between;gap:12px;border:1px solid var(--border);border-radius:12px;background:var(--bg);padding:12px 14px;text-decoration:none;color:inherit;min-width:0}
.analytics-row:hover{border-color:rgba(13,138,120,.35);box-shadow:0 8px 18px rgba(8,58,53,.07)}
.analytics-row strong{font-size:.85rem}.analytics-row small{display:block;color:var(--muted);font-size:.68rem;margin-top:3px}
.analytics-mini-chart{display:flex;align-items:end;gap:7px;height:130px;padding:14px;border:1px solid var(--border);border-radius:16px;background:linear-gradient(180deg,#fbfffd,#edf7f6)}
.analytics-bar{flex:1;min-width:4px;border-radius:999px 999px 4px 4px;background:linear-gradient(180deg,var(--teal),#81e6d9);opacity:.85;position:relative}
.analytics-bar.empty{background:#d9e8ea;opacity:.75}
.analytics-bar span{position:absolute;left:50%;bottom:-20px;transform:translateX(-50%);font-size:.58rem;color:var(--muted);font-family:'JetBrains Mono',monospace}
.moisture-compare-grid{display:grid;grid-template-columns:repeat(4,minmax(0,1fr));gap:12px}
.moisture-compare-card{border:1px solid var(--border);border-radius:16px;background:linear-gradient(180deg,#ffffff,#f7fcfb);padding:14px;min-width:0}
.moisture-compare-top{display:flex;align-items:center;justify-content:space-between;gap:8px;margin-bottom:12px}
.moisture-compare-title{font-weight:850;font-size:.86rem;color:var(--ink)}
.moisture-bars{height:108px;display:flex;align-items:end;gap:10px;padding:10px 8px 4px;border-radius:14px;background:linear-gradient(180deg,#f8fffd,#eef8f6);border:1px solid rgba(13,138,120,.11)}
.moisture-bar-wrap{flex:1;height:100%;display:flex;flex-direction:column;align-items:center;justify-content:end;gap:5px;min-width:0}
.moisture-bar{width:100%;max-width:34px;min-height:6px;border-radius:999px 999px 5px 5px;box-shadow:0 7px 16px rgba(8,58,53,.08)}
.moisture-bar.prev{background:linear-gradient(180deg,#bfd5d8,#dfecee)}
.moisture-bar.current{background:linear-gradient(180deg,var(--teal),#51d6c5)}
.moisture-bar.current.dry{background:linear-gradient(180deg,#ef4444,#fecaca)}
.moisture-bar.current.wet{background:linear-gradient(180deg,#f59e0b,#fde68a)}
.moisture-bar-label{font-size:.62rem;color:var(--muted);font-weight:800;text-transform:uppercase}
.moisture-value-row{display:flex;justify-content:space-between;gap:8px;margin-top:10px;font-size:.72rem;color:var(--muted)}
.moisture-priority-list{display:grid;gap:9px}
.moisture-priority-row{display:flex;align-items:center;justify-content:space-between;gap:12px;border:1px solid var(--border);border-radius:14px;background:var(--bg);padding:12px 14px}
.moisture-priority-row.dry{border-color:#fecaca;background:#fff7f7}
.moisture-priority-row.wet{border-color:#fde68a;background:#fffbeb}
.moisture-priority-row.offline{border-color:#dbe6ea;background:#f8fbfc}
.moisture-priority-row.ok{border-color:#b8efe7;background:#f1fffc}
.moisture-priority-row strong{font-size:.86rem}.moisture-priority-row small{display:block;color:var(--muted);font-size:.69rem;margin-top:3px}
.moisture-average-band{height:10px;border-radius:999px;background:linear-gradient(90deg,#ef4444 0 45%,#14b8a6 45% 65%,#f59e0b 65% 100%);margin-top:12px;position:relative;overflow:hidden}
.moisture-average-pin{position:absolute;top:-4px;width:18px;height:18px;border:3px solid #fff;border-radius:999px;background:var(--teal);box-shadow:0 4px 12px rgba(8,58,53,.25);transform:translateX(-50%)}
.farm-signal-chart{height:190px;border:1px solid var(--border);border-radius:18px;background:linear-gradient(180deg,#ffffff,#f4fbfa);padding:16px 14px 28px;display:flex;align-items:end;gap:8px;overflow:hidden}
.farm-signal-hour{flex:1;min-width:13px;height:100%;display:flex;align-items:end;justify-content:center;gap:3px;position:relative}
.farm-signal-stack{height:100%;display:flex;align-items:end;gap:3px}
.farm-signal-bar{width:7px;min-height:4px;border-radius:999px 999px 3px 3px;box-shadow:0 4px 10px rgba(8,58,53,.08)}
.farm-signal-bar.ripe{background:linear-gradient(180deg,#22c55e,#0d8a78)}
.farm-signal-bar.disease{background:linear-gradient(180deg,#ef4444,#b91c1c)}
.farm-signal-hour span{position:absolute;left:50%;bottom:-20px;transform:translateX(-50%);font-size:.58rem;color:var(--muted);font-family:'JetBrains Mono',monospace}
.farm-signal-legend{display:flex;gap:12px;flex-wrap:wrap;margin-top:12px;color:var(--muted);font-size:.75rem}
.farm-signal-legend b{display:inline-block;width:10px;height:10px;border-radius:999px;margin-right:6px;vertical-align:-1px}
.farm-signal-legend .ripe{background:#22c55e}.farm-signal-legend .disease{background:#ef4444}
.analytics-split{display:grid;grid-template-columns:1fr 1fr;gap:14px;align-items:stretch}
.analytics-empty{border:1px dashed var(--border);border-radius:16px;background:var(--bg);padding:28px;text-align:center;color:var(--muted);line-height:1.65}
.analytics-empty b{display:block;color:var(--text);font-size:1rem;margin-bottom:4px}
.storage-tree{border:1px solid var(--border);border-radius:18px;background:linear-gradient(180deg,#ffffff,#fbfffe);box-shadow:0 14px 34px rgba(8,58,53,.08);overflow:hidden}
.storage-tree-head{display:flex;align-items:center;justify-content:space-between;gap:12px;padding:13px 16px;background:linear-gradient(90deg,#eefaf7,#ffffff);border-bottom:1px solid var(--border);font-weight:900;color:var(--text)}
.storage-tree-body{padding:12px 14px 16px}
.storage-folder{position:relative;margin:1px 0}
.storage-folder-row{position:relative;display:flex;align-items:center;gap:9px;min-height:38px;padding:7px 10px;border-radius:12px;cursor:pointer;color:var(--text);transition:background .12s,border-color .12s,box-shadow .12s,transform .12s}
.storage-folder-row:hover{background:#eef8f7}
.storage-folder-row.event{border:1px solid rgba(96,143,157,.14);background:#fbfffe;margin:3px 0}
.storage-folder-row.event:hover{border-color:rgba(13,138,120,.28);box-shadow:0 7px 18px rgba(8,58,53,.07);transform:translateY(-1px)}
.storage-caret{width:18px;text-align:center;color:var(--teal-dk);font-family:'JetBrains Mono',monospace;font-size:.72rem;transition:transform .12s}
.storage-folder.open>.storage-folder-row>.storage-caret{transform:rotate(90deg)}
.storage-icon{width:26px;text-align:center;font-size:1.04rem;line-height:1;filter:saturate(1.08)}
.storage-icon .folder-open{display:none}
.storage-folder.open>.storage-folder-row .storage-icon .folder-closed{display:none}
.storage-folder.open>.storage-folder-row .storage-icon .folder-open{display:inline}
.storage-name{font-weight:850;min-width:0;overflow:hidden;text-overflow:ellipsis;white-space:nowrap;letter-spacing:.01em}
.storage-folder-row.event .storage-name{font-weight:800}
.storage-meta{margin-left:auto;color:var(--muted);font-size:.7rem;font-family:'JetBrains Mono',monospace;white-space:nowrap}
.storage-folder-children{display:none;position:relative;margin-left:32px;border-left:1px solid rgba(96,143,157,.24);padding-left:14px}
.storage-folder-children>.storage-folder:before{content:"";position:absolute;left:-14px;top:19px;width:14px;border-top:1px solid rgba(96,143,157,.24)}
.storage-folder.open>.storage-folder-children{display:block;animation:storageTreeOpen .14s ease-out}
.storage-event-body{display:none;margin:6px 0 11px 46px;padding:13px;border:1px solid var(--border);border-radius:14px;background:linear-gradient(180deg,#fbfffe,#f6fbfa)}
.storage-folder.open>.storage-event-body{display:block}
.storage-event-message{font-size:.79rem;color:var(--muted);margin-bottom:11px;line-height:1.55}
.storage-thumb-grid{display:grid;grid-template-columns:repeat(auto-fill,minmax(155px,1fr));gap:10px}
.storage-thumb-grid a{display:block;text-decoration:none}
.storage-thumb-grid img{width:100%;height:128px;object-fit:cover;border-radius:12px;border:1px solid var(--border);transition:transform .14s,box-shadow .14s}
.storage-thumb-grid a:hover img{transform:translateY(-2px);box-shadow:0 10px 22px rgba(8,58,53,.14)}
@keyframes storageTreeOpen{from{opacity:0;transform:translateY(-3px)}to{opacity:1;transform:translateY(0)}}
@media(max-width:640px){.storage-tree{border-radius:15px;box-shadow:0 8px 22px rgba(8,58,53,.07)}.storage-tree-head{padding:11px 12px;font-size:.9rem}.storage-tree-head .tag{font-size:.62rem;padding:5px 8px}.storage-tree-body{padding:8px 7px 11px}.storage-folder-row{min-height:44px;padding:8px 8px;gap:7px;border-radius:11px}.storage-caret{width:15px;font-size:.66rem}.storage-icon{width:23px;font-size:.98rem}.storage-name{white-space:normal;line-height:1.25;font-size:.84rem}.storage-meta{display:none}.storage-folder-children{margin-left:20px;padding-left:9px}.storage-folder-children>.storage-folder:before{left:-9px;width:9px;top:21px}.storage-event-body{margin:6px 0 10px 20px;padding:10px;border-radius:12px}.storage-event-message{font-size:.76rem}.storage-thumb-grid{grid-template-columns:1fr;gap:9px}.storage-thumb-grid img{height:auto;max-height:230px;object-fit:contain;background:#eef8f7}}
@media(max-width:860px){.analytics-hero,.analytics-split{grid-template-columns:1fr}.moisture-compare-grid{grid-template-columns:1fr 1fr}.farm-event-list{padding:12px}.analytics-tile{padding:15px}.farm-scan-grid,.farm-scan-steps,.farm-scan-findings{grid-template-columns:1fr}.farm-scan-btn{width:100%;margin-top:8px}.guard-strip{align-items:flex-start;gap:10px;flex-wrap:wrap}}
@media(max-width:520px){.moisture-compare-grid{grid-template-columns:1fr}.moisture-priority-row{align-items:flex-start;flex-direction:column}}
</style>
<script>
(function(){
  const PLANTS=['a','b','c','d','e','f','g','h'];
  function esc(v){return String(v??'').replace(/[&<>"']/g,m=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[m]));}
  function pct(v){return Math.round((Number(v)||0)*100);}
  function eventType(meta){
    const k=(meta&&meta.event_type)||'';
    if(k)return k;
    const l=String(meta&&meta.label||'').toLowerCase();
    if(l==='person'||l.includes('security'))return'security';
    if(l.includes('harvest')||l.includes('ripe'))return'ripeness';
    if(l.includes('health'))return'disease';
    return'unknown';
  }
  function eventInfo(kind,label){
    if(kind==='security')return{tag:'Security Farm',cls:'danger',mark:'!',title:'Security warning',text:'A person or animal event was stored for review.'};
    if(kind==='disease')return{tag:'Plant Health',cls:'danger',mark:'!',title:'Plant health warning',text:'Disease signs were detected. Inspect the affected area before harvest.'};
    if(kind==='disease_and_ripeness')return{tag:'Health + Harvest',cls:'warn',mark:'!',title:'Harvest ready, but check health',text:'Harvest signs and plant-health concern were detected in the same scan.'};
    if(kind==='ripeness')return{tag:'Harvest Ready',cls:'good',mark:'✓',title:'Good news: harvest signal',text:'Ready-to-harvest or flowering signs were detected.'};
    return{tag:'Stored Event',cls:'warn',mark:'i',title:label||'Stored event',text:'Saved event available for review.'};
  }
  function farmPanel(){return document.getElementById('camera-tab-farm');}
  function ensureFarmUi(){
    const panel=farmPanel(); if(!panel)return;
    const img=panel.querySelector('#farm-live-feed'); if(img&&img.getAttribute('src')!=='/farm_stream')img.setAttribute('src','/farm_stream');
    const strip=panel.querySelector('.guard-strip');
    if(strip&&!panel.querySelector('#farm-scan-now')){
      const btn=document.createElement('button');
      btn.id='farm-scan-now';btn.className='farm-scan-btn';btn.type='button';btn.textContent='Scan Now';
      btn.onclick=window.scanFarmNow;strip.appendChild(btn);
    }
    const chips=panel.querySelector('#farm-det-chips');
    if(chips&&!panel.querySelector('#farm-event-list')){
      chips.innerHTML='<div class="det-empty"><span>No plant health or harvest alert in the latest scan.</span></div>';
      chips.insertAdjacentHTML('afterend','<div class="farm-event-list" id="farm-event-list"></div>');
    }
    if(chips&&!panel.querySelector('#farm-scan-card')){
      chips.closest('.card').insertAdjacentHTML('beforebegin',`
        <div class="card" id="farm-scan-card">
          <div class="card-head"><span class="card-title">Farm Monitor Scan</span><span class="tag tag-grey" id="farm-scan-tag">Idle</span></div>
          <div class="farm-scan-grid">
            <div class="farm-scan-stat"><div class="farm-scan-k">Next Scan</div><div class="farm-scan-v" id="farm-scan-next">—</div></div>
            <div class="farm-scan-stat"><div class="farm-scan-k">Plant Health</div><div class="farm-scan-v" id="farm-scan-disease">No alert</div></div>
            <div class="farm-scan-stat"><div class="farm-scan-k">Harvest Signal</div><div class="farm-scan-v" id="farm-scan-ripe">Waiting</div></div>
          </div>
          <div class="farm-scan-progress">
            <div class="farm-scan-progress-top"><span id="farm-scan-stage">Waiting</span><span id="farm-scan-count">0/25 frames</span></div>
            <div class="farm-scan-progress-track"><span class="farm-scan-progress-bar" id="farm-scan-progress-bar"></span></div>
          </div>
          <div class="farm-scan-steps">
            <div class="farm-scan-step" data-farm-step="capture"><b>1. Capture frames</b><small id="farm-step-capture">Waiting for Scan Now.</small></div>
            <div class="farm-scan-step" data-farm-step="disease"><b>2. Plant Health</b><small id="farm-step-disease">Disease model ready.</small></div>
            <div class="farm-scan-step" data-farm-step="ripeness"><b>3. Harvest Signal</b><small id="farm-step-ripeness">Ripeness model ready.</small></div>
            <div class="farm-scan-step" data-farm-step="decision"><b>4. Decision</b><small id="farm-step-decision">Waiting for results.</small></div>
          </div>
          <div class="farm-scan-findings">
            <div class="farm-finding"><strong>Health warning frames</strong><span id="farm-find-disease">0 / 0</span><small>Disease or plant-health signs found by the health model.</small></div>
            <div class="farm-finding"><strong>Harvest signal frames</strong><span id="farm-find-ripe">0 / 0</span><small>Ripe, nearly ripe, or flowering signs found by the harvest model.</small></div>
          </div>
          <div class="farm-scan-note" id="farm-scan-message">Scheduled 6-hour scanning is ready.</div>
        </div>`);
    }
  }
  function renderFarmCards(result){
    const panel=farmPanel(); if(!panel)return;
    const list=panel.querySelector('#farm-event-list'); const chips=panel.querySelector('#farm-det-chips'); const tag=panel.querySelector('#farm-det-tag');
    if(!list)return;
    if(!result||!result.event_type||result.event_type==='clear'){
      list.innerHTML='<div class="farm-event-card"><div class="farm-event-mark">i</div><div><div class="farm-event-title">No current farm-monitor event</div><div class="farm-event-text">The latest scan did not find a sustained disease or harvest-readiness event.</div></div></div>';
      if(chips)chips.innerHTML='<div class="det-empty"><span>No plant health or harvest alert in the latest scan.</span></div>';
      if(tag){tag.textContent='Clear';tag.className='tag tag-safe';}
      return;
    }
    const kind=result.event_type; const cards=[];
    if(kind==='ripeness'||kind==='disease_and_ripeness'){
      const i=eventInfo('ripeness');
      cards.push(`<div class="farm-event-card ${i.cls}"><div class="farm-event-mark">${i.mark}</div><div><div class="farm-event-title">${i.title}</div><div class="farm-event-text">Harvest signal was seen in ${result.ripeness_frames||0} of ${result.usable_frames||0} usable frames. Best signal: ${esc((result.ripeness_best&&result.ripeness_best.label)||'Harvest ready')}.</div></div></div>`);
    }
    if(kind==='disease'||kind==='disease_and_ripeness'){
      const i=eventInfo('disease');
      cards.push(`<div class="farm-event-card ${i.cls}"><div class="farm-event-mark">${i.mark}</div><div><div class="farm-event-title">${i.title}</div><div class="farm-event-text">Plant-health alert was seen in ${result.disease_frames||0} of ${result.usable_frames||0} usable frames. Best alert: ${esc((result.disease_best&&result.disease_best.label)||'Plant health alert')}.</div></div></div>`);
    }
    list.innerHTML=cards.join('');
    if(chips)chips.innerHTML=`<div class="det-chip ${kind==='disease'?'person':'animal'}"><span>${esc(result.label||'Farm event')}</span></div>`;
    if(tag){tag.textContent=kind==='ripeness'?'Good News':(kind==='disease'?'Warning':'Review');tag.className=kind==='ripeness'?'tag tag-safe':(kind==='disease'?'tag tag-alert':'tag tag-warn');}
  }
  function fmtTime(iso){if(!iso)return'—';try{return new Date(iso).toLocaleString();}catch(_){return'—';}}
  function farmPct(n,d){n=Number(n)||0;d=Number(d)||0;return d?Math.max(0,Math.min(100,Math.round((n/d)*100))):0;}
  function farmSetText(sel,text){const el=farmPanel()?.querySelector(sel);if(el)el.textContent=text;}
  function farmSetProgress(s){
    const panel=farmPanel(); if(!panel)return;
    const total=Number(s&&s.target_frames)||25, captured=Number(s&&s.captured_frames)||0, usable=Number(s&&s.usable_frames)||0, skipped=Number(s&&s.skipped_frames)||0;
    let progress=0;
    if(s&&s.state==='scanning'){
      const cycle=Math.max(1,Number(s.current_cycle)||1), cycles=Math.max(1,Number(s.total_cycles)||2);
      const base=((cycle-1)/cycles)*100, slice=100/cycles;
      if(s.stage==='capture')progress=base+slice*0.35*farmPct(captured,total)/100;
      else if(s.stage==='disease_model')progress=base+slice*0.55;
      else if(s.stage==='ripeness_model')progress=base+slice*0.78;
      else if(s.stage==='cycle_summary')progress=base+slice*0.92;
      else if(s.stage==='decision')progress=96;
      else progress=base+8;
    }else if(s&&s.stage==='complete')progress=100;
    const bar=panel.querySelector('#farm-scan-progress-bar'); if(bar)bar.style.width=`${Math.round(progress)}%`;
    farmSetText('#farm-scan-stage', s&&s.stage?String(s.stage).replaceAll('_',' ').toUpperCase():'WAITING');
    farmSetText('#farm-scan-count', `${Math.min(captured,total)}/${total} frames`);
    farmSetText('#farm-step-capture', s&&s.state==='scanning'?`${usable} usable, ${skipped} skipped in cycle ${s.current_cycle||1}/${s.total_cycles||2}`:(s&&s.stage==='complete'?`${s.usable_frames||0} usable frames analyzed`:'Waiting for Scan Now.'));
    farmSetText('#farm-step-disease', s&&s.analyzing_model==='Plant Health model'?'Analyzing plant-health warnings now.':`${s&&s.disease_frames||0} warning frame(s) found.`);
    farmSetText('#farm-step-ripeness', s&&s.analyzing_model==='Harvest Readiness model'?'Analyzing harvest readiness now.':`${s&&s.ripeness_frames||0} harvest-signal frame(s) found.`);
    farmSetText('#farm-step-decision', s&&s.stage==='decision'?'Combining both model results.':(s&&s.stage==='complete'?'Final scan decision complete.':'Waiting for model results.'));
    farmSetText('#farm-find-disease', `${s&&s.disease_frames||0} / ${s&&s.usable_frames||0}`);
    farmSetText('#farm-find-ripe', `${s&&s.ripeness_frames||0} / ${s&&s.usable_frames||0}`);
    panel.querySelectorAll('.farm-scan-step').forEach(x=>x.classList.remove('active','done','warn'));
    const stage=s&&s.stage;
    const capture=panel.querySelector('[data-farm-step="capture"]'), disease=panel.querySelector('[data-farm-step="disease"]'), ripe=panel.querySelector('[data-farm-step="ripeness"]'), decision=panel.querySelector('[data-farm-step="decision"]');
    if(stage==='capture')capture&&capture.classList.add('active');
    if(stage==='disease_model'){capture&&capture.classList.add('done');disease&&disease.classList.add('active');}
    if(stage==='ripeness_model'){capture&&capture.classList.add('done');disease&&disease.classList.add('done');ripe&&ripe.classList.add('active');}
    if(stage==='cycle_summary'||stage==='decision'){capture&&capture.classList.add('done');disease&&disease.classList.add('done');ripe&&ripe.classList.add('done');decision&&decision.classList.add('active');}
    if(stage==='complete'){[capture,disease,ripe,decision].forEach(x=>x&&x.classList.add('done'));}
    if(stage==='error'){[capture,disease,ripe,decision].forEach(x=>x&&x.classList.add('warn'));}
  }
  function applyFarmStatusClean(s){
    ensureFarmUi();
    const panel=farmPanel(); if(!panel)return;
    const result=s&&s.last_result?s.last_result:null;
    const tag=panel.querySelector('#farm-scan-tag'), msg=panel.querySelector('#farm-scan-message'), next=panel.querySelector('#farm-scan-next'), dis=panel.querySelector('#farm-scan-disease'), ripe=panel.querySelector('#farm-scan-ripe'), btn=panel.querySelector('#farm-scan-now');
    const label=panel.querySelector('#guard-label'), sub=panel.querySelector('#guard-sub');
    if(tag){tag.textContent=(s&&s.state?s.state:'idle').toUpperCase();tag.className=s&&s.state==='scanning'?'tag tag-warn':(s&&s.state==='error'?'tag tag-alert':'tag tag-teal');}
    if(msg)msg.textContent=(s&&s.message)||'Scheduled 6-hour scanning is ready.';
    if(next)next.textContent=fmtTime(s&&s.next_scan_at);
    if(dis)dis.textContent=result?(result.event_type==='disease'||result.event_type==='disease_and_ripeness'?'Warning':'No alert'):'No alert';
    if(ripe)ripe.textContent=result?(result.event_type==='ripeness'||result.event_type==='disease_and_ripeness'?'Ready':'Waiting'):'Waiting';
    if(btn)btn.disabled=!!(s&&s.state==='scanning');
    if(label)label.textContent='Farm Monitor';
    if(sub)sub.textContent=s&&s.state==='scanning'?'Scanning captured frames':((s&&s.message)||'Plant health and harvest monitoring are ready');
    farmSetProgress(s||{});
    renderFarmCards(result);
  }
  window.loadFarmMonitorStatus=async function(){
    try{const r=await fetch('/api/farm_monitor/status');if(!r.ok)return;applyFarmStatusClean(await r.json());}catch(_){}
  };
  window.scanFarmNow=async function(){
    ensureFarmUi();
    const btn=farmPanel()?.querySelector('#farm-scan-now');
    if(btn){btn.disabled=true;btn.textContent='Scanning...';}
    try{
      const r=await fetch('/api/farm_monitor/scan_now',{method:'POST'});
      const d=await r.json();
      if(window.showToast)showToast(d.message||'Farm Monitor scan queued');
      if(d.status)applyFarmStatusClean(d.status);
    }catch(_){if(window.showToast)showToast('Farm Monitor scan request failed');}
    finally{if(btn){btn.textContent='Scan Now';setTimeout(()=>window.loadFarmMonitorStatus(),1500);}}
  };
  const oldHandle=window.handleState;
  if(typeof oldHandle==='function'&&!oldHandle.__cleanFarmPatch){
    const wrapped=function(d){oldHandle(d);if(d&&d.farm_monitor){applyFarmStatusClean(d.farm_monitor);if(d.farm_monitor.stage==='complete'||d.farm_monitor.state==='idle')setTimeout(loadPlantHealthOverview,600);}};
    wrapped.__cleanFarmPatch=true;window.handleState=wrapped;
  }
  function flattenStorage(tree){
    const out=[]; for(const yr of Object.keys(tree||{}).sort().reverse())for(const mo of Object.keys(tree[yr]||{}).sort().reverse())for(const day of Object.keys(tree[yr][mo]||{}).sort().reverse())for(const evt of (tree[yr][mo][day]||[]).slice().reverse()){
      out.push({yr,mo,day,time:evt.time,meta:evt.meta||{},images:evt.images||[]});
    } return out;
  }
  function eventImageUrl(evt){
    return evt&&evt.images&&evt.images.length?`/storage_img/${evt.yr}/${evt.mo}/${evt.day}/${evt.time}/${evt.images[0]}`:'';
  }
  function eventDateText(evt){
    return `${evt.yr}/${evt.mo}/${evt.day} ${String(evt.time||'').replaceAll('-',':')}`;
  }
  function hourlyChart(hourly){
    const vals=Array.from({length:24},(_,h)=>Number((hourly||{})[String(h)]||0));
    const max=Math.max(1,...vals);
    return `<div class="analytics-mini-chart">${vals.map((v,h)=>`<div class="analytics-bar ${v?'':'empty'}" style="height:${Math.max(8,Math.round((v/max)*112))}px" title="${h}:00 - ${v} event${v===1?'':'s'}"><span>${h%6===0?String(h).padStart(2,'0'):''}</span></div>`).join('')}</div>`;
  }
  function farmSignalStats(events){
    const byHour=Array.from({length:24},()=>({ripe:0,disease:0,total:0}));
    let ripe=0,disease=0,combined=0;
    for(const e of events){
      const k=eventType(e.meta);
      let h=0;
      try{h=new Date((e.meta&&e.meta.time)||`${e.yr}-${e.mo}-${e.day}T${String(e.time||'00-00-00').replaceAll('-',':')}`).getHours();if(Number.isNaN(h))h=0;}catch(_){h=0;}
      if(k==='ripeness'){ripe++;byHour[h].ripe++;byHour[h].total++;}
      else if(k==='disease'){disease++;byHour[h].disease++;byHour[h].total++;}
      else if(k==='disease_and_ripeness'){combined++;ripe++;disease++;byHour[h].ripe++;byHour[h].disease++;byHour[h].total+=2;}
    }
    return{ripe,disease,combined,byHour,max:Math.max(1,...byHour.map(v=>v.total))};
  }
  function farmSignalChart(stats){
    return `<div><div class="farm-signal-chart">${stats.byHour.map((v,h)=>{
      const rh=Math.max(v.ripe?8:3,Math.round((v.ripe/stats.max)*148));
      const dh=Math.max(v.disease?8:3,Math.round((v.disease/stats.max)*148));
      return `<div class="farm-signal-hour" title="${String(h).padStart(2,'0')}:00 · harvest ${v.ripe}, disease ${v.disease}"><div class="farm-signal-stack"><div class="farm-signal-bar ripe" style="height:${rh}px;opacity:${v.ripe?1:.14}"></div><div class="farm-signal-bar disease" style="height:${dh}px;opacity:${v.disease?1:.14}"></div></div><span>${h%6===0?String(h).padStart(2,'0'):''}</span></div>`;
    }).join('')}</div><div class="farm-signal-legend"><span><b class="ripe"></b>Ripeness / harvest signal</span><span><b class="disease"></b>Disease / plant health warning</span></div></div>`;
  }
  function storageFolder(name,meta,children,open=false,extra=''){
    return `<div class="storage-folder ${open?'open':''}"><div class="storage-folder-row" onclick="this.parentElement.classList.toggle('open')"><span class="storage-caret">▶</span><span class="storage-icon"><span class="folder-closed">📁</span><span class="folder-open">📂</span></span><span class="storage-name">${esc(name)}</span><span class="storage-meta">${esc(meta)}</span></div><div class="storage-folder-children">${children}</div>${extra}</div>`;
  }
  function storageEventFolder(evt,open=false){
    const kind=eventType(evt.meta), info=eventInfo(kind,evt.meta.label);
    const eventName=`${evt.time}  ${info.tag}`;
    const meta=[evt.meta.label||info.title,`${evt.images.length} image${evt.images.length===1?'':'s'}`].filter(Boolean).join(' · ');
    const imgs=evt.images.map(img=>{
      const u=`/storage_img/${evt.yr}/${evt.mo}/${evt.day}/${evt.time}/${img}`;
      return `<a href="${u}" target="_blank" rel="noopener" title="Open ${esc(img)}"><img src="${u}" alt="${esc(img)}"></a>`;
    }).join('');
    const body=`<div class="storage-event-message">${esc(evt.meta.message||info.text)}<br><span class="storage-meta">${esc(evt.yr+'/'+evt.mo+'/'+evt.day+' '+String(evt.time||'').replaceAll('-',':'))}</span></div>${imgs?`<div class="storage-thumb-grid">${imgs}</div>`:'<div class="analytics-empty"><b>No image attached</b>This event has metadata only.</div>'}`;
    return `<div class="storage-folder ${open?'open':''}"><div class="storage-folder-row event" onclick="this.parentElement.classList.toggle('open')"><span class="storage-caret">▶</span><span class="storage-icon"><span class="folder-closed">📁</span><span class="folder-open">📂</span></span><span class="storage-name">${esc(eventName)}</span><span class="storage-meta">${esc(meta)}</span></div><div class="storage-event-body">${body}</div></div>`;
  }
  window.renderStorageTree=function(tree,container){
    const years=Object.keys(tree||{}).sort().reverse();
    if(!years.length){container.innerHTML='<div class="analytics-empty"><b>No data saved yet</b>Storage will fill automatically when security, harvest, disease, or irrigation events occur.</div>';return;}
    const latest={yr:years[0],mo:null,day:null,time:null};
    latest.mo=Object.keys(tree[latest.yr]||{}).sort().reverse()[0];
    latest.day=Object.keys(((tree[latest.yr]||{})[latest.mo]||{})).sort().reverse()[0];
    const latestEvents=((((tree[latest.yr]||{})[latest.mo]||{})[latest.day])||[]).slice().sort((a,b)=>String(b.time||'').localeCompare(String(a.time||'')));
    latest.time=latestEvents[0]&&latestEvents[0].time;
    const total=flattenStorage(tree).length;
    const yearHtml=years.map(yr=>{
      const months=Object.keys(tree[yr]||{}).sort().reverse();
      const yearCount=months.reduce((a,mo)=>a+Object.values(tree[yr][mo]||{}).reduce((b,arr)=>b+(arr||[]).length,0),0);
      const monthHtml=months.map(mo=>{
        const days=Object.keys(tree[yr][mo]||{}).sort().reverse();
        const monthCount=days.reduce((a,day)=>a+(tree[yr][mo][day]||[]).length,0);
        const dayHtml=days.map(day=>{
          const events=(tree[yr][mo][day]||[]).slice().sort((a,b)=>String(b.time||'').localeCompare(String(a.time||'')));
          const eventHtml=events.map(evt=>storageEventFolder({yr,mo,day,time:evt.time,meta:evt.meta||{},images:evt.images||[]},yr===latest.yr&&mo===latest.mo&&day===latest.day&&evt.time===latest.time)).join('');
          return storageFolder(day,`${events.length} event${events.length===1?'':'s'}`,eventHtml,yr===latest.yr&&mo===latest.mo&&day===latest.day);
        }).join('');
        return storageFolder(mo,`${monthCount} event${monthCount===1?'':'s'}`,dayHtml,yr===latest.yr&&mo===latest.mo);
      }).join('');
      return storageFolder(yr,`${yearCount} event${yearCount===1?'':'s'}`,monthHtml,yr===latest.yr);
    }).join('');
    container.innerHTML=`<div class="storage-tree"><div class="storage-tree-head"><span><span style="margin-right:7px">📂</span>Storage_Data</span><span class="tag tag-teal">${total} EVENT${total===1?'':'S'}</span></div><div class="storage-tree-body">${yearHtml}</div></div>`;
  };
  function onlineCount(d){
    const st=d.sensor_status||{}, cur=d.moisture_current||{};
    return PLANTS.filter(p=>st[p]&&st[p].online===true&&cur[p]!==null&&cur[p]!==undefined).length;
  }
  function moistureState(v,on){
    if(!on)return {key:'offline',tag:'OFFLINE',label:'Sensor offline',cls:'tag-grey'};
    if(v<45)return {key:'dry',tag:'IRRIGATE',label:'Needs irrigation',cls:'tag-alert'};
    if(v>65)return {key:'wet',tag:'OVER',label:'Over irrigated',cls:'tag-warn'};
    return {key:'ok',tag:'BALANCED',label:'Healthy moisture range',cls:'tag-teal'};
  }
  function moistureLatestPair(d,p){
    const hist=(d.moisture_history&&d.moisture_history[p])||[];
    const cur=d.moisture_current&&d.moisture_current[p];
    const current=cur!==null&&cur!==undefined?Number(cur):(hist.length?Number(hist[hist.length-1].v):null);
    let previous=null;
    if(hist.length>1)previous=Number(hist[hist.length-2].v);
    else if(hist.length===1)previous=Number(hist[0].v);
    return {previous:Number.isFinite(previous)?previous:null,current:Number.isFinite(current)?current:null};
  }
  function moisturePercent(v){
    return v===null||v===undefined||!Number.isFinite(Number(v))?'--':`${Math.round(Number(v))}%`;
  }
  function moistureCompareCard(d,p){
    const st=d.sensor_status&&d.sensor_status[p], pair=moistureLatestPair(d,p);
    const on=st&&st.online===true&&pair.current!==null&&pair.current!==undefined;
    const state=moistureState(pair.current,on);
    const prev=pair.previous!==null?Math.max(3,Math.min(100,Math.round(pair.previous))):3;
    const cur=pair.current!==null?Math.max(3,Math.min(100,Math.round(pair.current))):3;
    return `<div class="moisture-compare-card"><div class="moisture-compare-top"><span class="moisture-compare-title">Plant ${p.toUpperCase()}</span><span class="tag ${state.cls}">${state.tag}</span></div><div class="moisture-bars"><div class="moisture-bar-wrap"><div class="moisture-bar prev" style="height:${prev}%"></div><span class="moisture-bar-label">Prev</span></div><div class="moisture-bar-wrap"><div class="moisture-bar current ${state.key}" style="height:${cur}%"></div><span class="moisture-bar-label">Now</span></div></div><div class="moisture-value-row"><span>${moisturePercent(pair.previous)}</span><strong>${moisturePercent(pair.current)}</strong></div><div class="analytics-note">${state.label}</div></div>`;
  }
  function moisturePriorityRows(items){
    const priority=items.filter(x=>x.state.key!=='ok');
    if(!priority.length){
      return '<div class="moisture-priority-row ok"><div><strong>All reporting plants are balanced</strong><small>No irrigation action is needed from current readings.</small></div><span class="tag tag-teal">OK</span></div>';
    }
    return priority.map(x=>`<div class="moisture-priority-row ${x.state.key}"><div><strong>Plant ${x.plant.toUpperCase()}</strong><small>${x.state.key==='dry'?'Below 45% dryness threshold - start irrigation.':x.state.key==='wet'?'Above 65% - pause watering and monitor drainage.':'Sensor offline - check wiring or ADS1115 channel.'}</small></div><span class="tag ${x.state.cls}">${x.state.key==='offline'?'OFFLINE':moisturePercent(x.current)}</span></div>`).join('');
  }
  function renderModernAnalytics(d,tree){
    const events=flattenStorage(tree||{}), summary=d.storage_summary||{};
    const online=onlineCount(d), latest=d.latest_farm_event;
    const moisture=document.getElementById('tab-moisture'), security=document.getElementById('tab-intruder'), health=document.getElementById('tab-planthealth');
    if(moisture){
      const items=PLANTS.map(p=>{
        const st=d.sensor_status&&d.sensor_status[p], pair=moistureLatestPair(d,p);
        const on=st&&st.online===true&&pair.current!==null&&pair.current!==undefined;
        return {plant:p,current:pair.current,previous:pair.previous,on,state:moistureState(pair.current,on)};
      });
      const onlineVals=items.filter(x=>x.on).map(x=>Number(x.current));
      const avg=onlineVals.length?Math.round(onlineVals.reduce((a,b)=>a+b,0)/onlineVals.length):null;
      const dry=items.filter(x=>x.state.key==='dry').length, wet=items.filter(x=>x.state.key==='wet').length, offline=items.filter(x=>x.state.key==='offline').length;
      const avgState=moistureState(avg,avg!==null);
      const avgPin=avg!==null?Math.max(2,Math.min(98,avg)):0;
      if(!online){
        moisture.innerHTML=`<div class="analytics-modern"><div class="analytics-hero"><div class="analytics-tile" style="border-color:#fecaca;background:linear-gradient(135deg,#fff7f7,#ffffff)"><div class="analytics-k">Moisture Sensors</div><div class="analytics-v" style="color:#b91c1c">Offline</div><div class="analytics-note">No ADS1115 moisture sensor data is currently being read.</div></div><div class="analytics-tile"><div class="analytics-k">Average Moisture</div><div class="analytics-v">--%</div><div class="analytics-note">Average is hidden until at least one real sensor reports.</div></div><div class="analytics-tile"><div class="analytics-k">Irrigation Decision</div><div class="analytics-v" style="color:#6b8792">Paused</div><div class="analytics-note">No watering recommendation is made from missing sensor data.</div></div></div><div class="card"><div class="card-head"><span class="card-title">Sensor Offline</span><span class="tag tag-alert">CHECK SENSORS</span></div><div class="card-body"><div class="analytics-empty"><b>Moisture sensors are offline</b>Connect/check the ADS1115 moisture sensor wiring. This analytics page will show previous vs current graphs only after real readings are available.</div></div></div></div>`;
      } else {
      moisture.innerHTML=`<div class="analytics-modern"><div class="analytics-hero"><div class="analytics-tile"><div class="analytics-k">Average Moisture</div><div class="analytics-v">${avg!==null?avg+'%':'--%'}</div><div class="analytics-note">${online?online+' sensors included in the average':'Sensors offline - no moisture average available.'}</div><div class="moisture-average-band"><span class="moisture-average-pin" style="left:${avgPin}%"></span></div></div><div class="analytics-tile"><div class="analytics-k">Need Irrigation</div><div class="analytics-v" style="color:#b91c1c">${dry}</div><div class="analytics-note">Plants below 45% are marked for watering.</div></div><div class="analytics-tile"><div class="analytics-k">Over Irrigated</div><div class="analytics-v" style="color:#b45309">${wet}</div><div class="analytics-note">Plants above 65% should pause irrigation.</div></div></div><div class="card"><div class="card-head"><span class="card-title">Moisture Trend by Plant</span><span class="tag ${avgState.cls}">${avgState.tag}</span></div><div class="card-body"><div class="moisture-compare-grid">${PLANTS.map(p=>moistureCompareCard(d,p)).join('')}</div></div></div><div class="card"><div class="card-head"><span class="card-title">Irrigation Priority</span><span class="tag ${offline?'tag-grey':'tag-teal'}">${offline?offline+' OFFLINE':'LIVE'}</span></div><div class="card-body"><div class="moisture-priority-list">${moisturePriorityRows(items)}</div></div></div></div>`;
      }
    }
    if(security){
      const allSecEvents=events.filter(e=>eventType(e.meta)==='security');const secEvents=allSecEvents.slice(0,8);const secHourly=Object.fromEntries(Array.from({length:24},(_,h)=>[String(h),allSecEvents.filter(e=>parseInt((e.time||'00').split('-')[0],10)===h).length]));
      security.innerHTML=`<div class="analytics-modern"><div class="analytics-hero"><div class="analytics-tile"><div class="analytics-k">Total Security Events</div><div class="analytics-v">${allSecEvents.length}</div><div class="analytics-note">Events are saved only when guard is active.</div></div><div class="analytics-tile"><div class="analytics-k">Camera Separation</div><div class="analytics-v">Clean</div><div class="analytics-note">Security camera does not use FarmMonitor camera work.</div></div><div class="analytics-tile"><div class="analytics-k">Stored Evidence</div><div class="analytics-v">${allSecEvents.length}</div><div class="analytics-note">Click Review to open the stored event image.</div></div></div><div class="analytics-split"><div class="card"><div class="card-head"><span class="card-title">Security Events by Hour</span><span class="tag tag-grey">All Stored</span></div><div class="card-body">${hourlyChart(secHourly)}</div></div><div class="card"><div class="card-head"><span class="card-title">Recent Security Events</span><span class="tag tag-grey">Last stored</span></div><div class="card-body">${secEvents.length?'<div class="analytics-list">'+secEvents.map(e=>{const u=eventImageUrl(e);const row=`<div><strong>${esc(e.meta.label&&e.meta.label!=='person'?e.meta.label:'Security activity')}</strong><small>${eventDateText(e)}</small></div><span class="tag tag-alert">Review</span>`;return u?`<a class="analytics-row" href="${u}" target="_blank" rel="noopener">${row}</a>`:`<div class="analytics-row">${row}</div>`}).join('')+'</div>':'<div class="analytics-empty"><b>No active security events</b>Security events appear here only after guard is turned ON and a threat is detected.</div>'}</div></div></div></div>`;
    }
    if(health){
      const farmEvents=events.filter(e=>['disease','ripeness','disease_and_ripeness'].includes(eventType(e.meta))).slice(0,8);
      const allFarmEvents=events.filter(e=>['disease','ripeness','disease_and_ripeness'].includes(eventType(e.meta)));
      const stats=farmSignalStats(allFarmEvents);
      health.innerHTML=`<div class="analytics-modern"><div class="analytics-hero"><div class="analytics-tile"><div class="analytics-k">Disease Warnings</div><div class="analytics-v" style="color:#b91c1c">${stats.disease}</div><div class="analytics-note">Red bars show when plant-health warnings were stored.</div></div><div class="analytics-tile"><div class="analytics-k">Ripeness Signals</div><div class="analytics-v" style="color:#0d8a78">${stats.ripe}</div><div class="analytics-note">Green bars show harvest-readiness frequency.</div></div><div class="analytics-tile"><div class="analytics-k">Combined Events</div><div class="analytics-v" style="color:#b45309">${stats.combined}</div><div class="analytics-note">Both harvest and health warning appeared together.</div></div></div><div class="card"><div class="card-head"><span class="card-title">Plant Health & Harvest Timeline</span><span class="tag tag-teal">By hour</span></div><div class="card-body">${farmSignalChart(stats)}</div></div><div class="card"><div class="card-head"><span class="card-title">Stored FarmMonitor Events</span><span class="tag tag-teal">Evidence linked</span></div><div class="card-body">${farmEvents.length?'<div class="analytics-list">'+farmEvents.map(e=>{const i=eventInfo(eventType(e.meta),e.meta.label);const u=eventImageUrl(e);const row=`<div><strong>${esc(e.meta.label||i.title)}</strong><small>${eventDateText(e)} · ${esc(e.meta.message||i.text)}</small></div><span class="tag ${i.cls==='danger'?'tag-alert':i.cls==='good'?'tag-safe':'tag-warn'}">${esc(i.tag)}</span>`;return u?`<a class="analytics-row" href="${u}" target="_blank" rel="noopener">${row}</a>`:`<div class="analytics-row">${row}</div>`}).join('')+'</div>':'<div class="analytics-empty"><b>No FarmMonitor event stored yet</b>Run Scan Now from Farm Monitor when strawberry images are in view. This page will then show disease and ripeness frequency over time.</div>'}</div></div></div>`;
    }
  }
  window.loadAnalytics=async function(){
    try{
      const [a,s]=await Promise.all([fetch('/api/analytics').then(r=>r.json()),fetch('/api/storage').then(r=>r.json()).catch(()=>({}))]);
      renderModernAnalytics(a,s);
      try{analyticsLoaded=true;}catch(_){}
    }catch(e){console.warn('analytics failed',e);}
  };
  document.addEventListener('DOMContentLoaded',()=>{ensureFarmUi();window.loadFarmMonitorStatus();});
})();
</script>
<script>
/* AIgriculture home: stream manager + plant health overview + real events */
(function(){
  var BLANK='data:image/gif;base64,R0lGODlhAQABAIAAAAAAAP///yH5BAEAAAAALAAAAAABAAEAAAIBRAA7';

  function initStreamMgr(){
    var lf=document.getElementById('live-feed');
    var cam=document.getElementById('page-camera');
    if(!lf||!cam)return;
    function applyStream(on){
      if(on){
        if(lf.src===BLANK||lf.src.indexOf('/stream')===-1){
          lf.style.display='block';
          try{document.getElementById('cam-placeholder').style.display='none';}catch(_){}
          lf.src='/stream';
        }
      }else{
        if(lf.src.indexOf('/stream')!==-1){
          lf.src=BLANK; lf.style.display='none';
          try{document.getElementById('cam-placeholder').style.display='flex';}catch(_){}
        }
      }
    }
    applyStream(cam.classList.contains('active'));
    new MutationObserver(function(ms){
      ms.forEach(function(m){if(m.attributeName==='class')applyStream(cam.classList.contains('active'));});
    }).observe(cam,{attributes:true});
  }

  function fmtAgo(iso){
    if(!iso)return 'No scans';
    var dt=new Date(iso),now=new Date(),dh=Math.floor((now-dt)/3600000),dd=Math.floor(dh/24);
    return dd>0?dd+'d ago':dh>0?dh+'h ago':'Today';
  }

  async function loadPlantHealthOverview(){
    var body=document.getElementById('ph-ov-body');
    var tag=document.getElementById('ph-ov-tag');
    if(!body)return;
    try{
      var storageReq=fetch('/api/storage',{cache:'no-store'}).then(function(r){return r.ok?r.json():{};}).catch(function(){return{};});
      var statusReq=fetch('/api/farm_monitor/status',{cache:'no-store'}).then(function(r){return r.ok?r.json():{};}).catch(function(){return{};});
      var both=await Promise.all([storageReq,statusReq]);
      var tree=both[0]||{}, fm=both[1]||{};
      var events=typeof flattenStorage==='function'?flattenStorage(tree):[];
      function k(meta){
        var et=String(meta&&meta.event_type||'').toLowerCase();
        if(et)return et;
        var l=String(meta&&meta.label||'').toLowerCase();
        if(l.includes('harvest')||l.includes('ripe')||l.includes('flower'))return 'ripeness';
        if(l.includes('disease')||l.includes('health')||l.includes('mold')||l.includes('spot')||l.includes('rot'))return 'disease';
        return '';
      }
      function isFarm(e){var m=e&&e.meta||{};var l=String(m.label||'');var et=String(m.event_type||'');return l.indexOf('FarmMonitor:')===0||et==='disease'||et==='ripeness'||et==='disease_and_ripeness';}
      function t(e){try{return new Date((e.meta&&e.meta.time)||`${e.yr}-${e.mo}-${e.day}T${String(e.time||'00-00-00').replaceAll('-',':')}`).getTime()||0;}catch(_){return 0;}}
      var farmEvents=events.filter(isFarm).sort(function(a,b){return t(a)-t(b);});
      var dEvs=farmEvents.filter(function(e){var x=k(e.meta);return x==='disease'||x==='disease_and_ripeness';});
      var rEvs=farmEvents.filter(function(e){var x=k(e.meta);return x==='ripeness'||x==='disease_and_ripeness';});
      var all=dEvs.concat(rEvs).sort(function(a,b){return t(a)-t(b);});
      var last=all.length?all[all.length-1]:null;
      var ld=dEvs.length?dEvs[dEvs.length-1]:null;
      var lr=rEvs.length?rEvs[rEvs.length-1]:null;
      var scanIso=(fm&&fm.completed_at)||(fm&&fm.last_scan_at)||(last&&last.meta&&last.meta.time)||'';
      var scanStr=scanIso?fmtAgo(scanIso):'No scans yet';
      var dLbl=ld&&ld.meta&&ld.meta.disease_best?ld.meta.disease_best.label:'';
      var rLbl=lr&&lr.meta&&lr.meta.ripeness_best?lr.meta.ripeness_best.label:'';
      if(tag){
        if(fm&&fm.state==='scanning'){tag.className='tag tag-warn';tag.textContent='Scanning';}
        else if(dEvs.length){tag.className='tag tag-alert';tag.textContent='Disease Alert';}
        else if(rEvs.length){tag.className='tag tag-safe';tag.textContent='Harvest Ready';}
        else{tag.className='tag tag-grey';tag.textContent='No Scans';}
      }
      body.innerHTML=
        '<div style="display:grid;grid-template-columns:1fr 1fr;gap:8px;margin-bottom:10px">'
        +'<div style="background:linear-gradient(135deg,#fef2f2,#fee2e2);border:1px solid #fca5a5;border-radius:10px;padding:10px 12px;text-align:center">'
        +'<div style="font-family:\'JetBrains Mono\',monospace;font-size:1.3rem;font-weight:800;color:#b91c1c;line-height:1">'+dEvs.length+'</div>'
        +'<div style="font-size:.6rem;color:#991b1b;font-weight:800;letter-spacing:.5px;margin-top:3px;text-transform:uppercase">Disease Alerts</div>'
        +(dLbl?'<div style="font-size:.6rem;color:#b91c1c;margin-top:4px;opacity:.9;white-space:nowrap;overflow:hidden;text-overflow:ellipsis">'+dLbl+'</div>':'')
        +'</div>'
        +'<div style="background:linear-gradient(135deg,#ecfdf5,#d1fae5);border:1px solid #6ee7b7;border-radius:10px;padding:10px 12px;text-align:center">'
        +'<div style="font-family:\'JetBrains Mono\',monospace;font-size:1.3rem;font-weight:800;color:#065f46;line-height:1">'+rEvs.length+'</div>'
        +'<div style="font-size:.6rem;color:#065f46;font-weight:800;letter-spacing:.5px;margin-top:3px;text-transform:uppercase">Harvest Signals</div>'
        +(rLbl?'<div style="font-size:.6rem;color:#065f46;margin-top:4px;opacity:.9;white-space:nowrap;overflow:hidden;text-overflow:ellipsis">'+rLbl+'</div>':'')
        +'</div>'
        +'</div>'
        +'<div style="display:flex;align-items:center;justify-content:space-between;gap:10px;padding:7px 0;border-top:1px solid var(--border)">'
        +'<span style="font-size:.72rem;color:var(--muted)">Last scan: <strong style="color:var(--text)">'+scanStr+'</strong></span>'
        +'<a href="#" onclick="showAnalyticsMode(\'planthealth\',document.querySelector(\'#analytics-sub .nav-sub-item[onclick*=planthealth]\'));return false;" style="font-size:.7rem;color:var(--teal);font-weight:700;text-decoration:none;white-space:nowrap">View Analytics &#x2192;</a>'
        +'</div>';
    }catch(err){
      if(body)body.innerHTML='<div style="text-align:center;color:var(--muted);font-size:.76rem;padding:14px 0">Plant health data unavailable</div>';
    }
  }

  async function loadRecentEventsFromStorage(){
    var list=document.getElementById('events-list');
    if(!list)return;
    try{
      var tree=await fetch('/api/storage').then(function(r){return r.ok?r.json():{};}).catch(function(){return{};});
      var events=typeof flattenStorage==='function'?flattenStorage(tree):[];
      if(!events.length){
        list.innerHTML='<div class="ev-row"><div class="ev-dot" style="background:var(--muted)"></div><span style="color:var(--muted);font-size:.77rem">No events recorded</span></div>';
        return;
      }
      var recent=events.slice(-5).reverse();
      list.innerHTML=recent.map(function(ev){
        var m=ev.meta||{};
        var et=m.event_type||(m.label==='person'?'security':'unknown');
        var label=et==='security'?'Security Alert'
          :et==='disease'?(m.disease_best?m.disease_best.label:'Disease Alert')
          :et==='ripeness'?(m.ripeness_best?m.ripeness_best.label:'Harvest Signal')
          :m.label||'Event';
        var dc=et==='security'?'var(--danger)':et==='disease'?'#b91c1c':et==='ripeness'?'var(--teal)':'var(--muted)';
        var ts='';
        if(m.time){var dt=new Date(m.time),now=new Date(),dh=Math.floor((now-dt)/3600000),dd=Math.floor(dh/24);ts=dd>0?dd+'d':dh>0?dh+'h':'now';}
        return '<div class="ev-row"><div class="ev-dot" style="background:'+dc+'"></div>'
          +'<span style="font-size:.77rem">'+label+'</span>'
          +'<span class="ev-time">'+ts+'</span></div>';
      }).join('');
    }catch(err){}
  }

  document.addEventListener('DOMContentLoaded',function(){
    initStreamMgr();
    loadPlantHealthOverview();
    loadRecentEventsFromStorage();
    setInterval(loadPlantHealthOverview,10000);
  });
})();
</script>
"""

def _inject_farm_monitor_ui_patch(html: str) -> str:
    if "__farmMonitorPatch" in html:
        return html
    if "</body>" in html:
        return html.replace("</body>", FARM_MONITOR_UI_PATCH + "</body>")
    return html + FARM_MONITOR_UI_PATCH

def _inject_dashboard_integration_patch(html: str) -> str:
    if "farm-event-list" in html and "analytics-modern" in html:
        return html
    if "</body>" in html:
        return html.replace("</body>", DASHBOARD_INTEGRATION_PATCH + "</body>")
    return html + DASHBOARD_INTEGRATION_PATCH


# Card spacing polish — applied UNCONDITIONALLY since the original theme has no
# matching guard token. Adds breathing room between cards / sections so a tiny
# "Plant A + Plant B only" deployment doesn't feel cramped. CSS variables,
# colours, fonts, radii — all untouched.
SPACING_POLISH_PATCH = r"""
<style data-aig-spacing-polish>
.home-grid{gap:18px}
.plant-grid{gap:20px;margin-bottom:18px}
.plant-card{padding:18px 22px}
.avg-strip{margin-bottom:18px}
.avg-strip .avg-right{gap:14px;flex-wrap:wrap}
#btn-add-sensor{margin-left:auto}
.home-right > * + *{margin-top:14px}
</style>
"""

def _inject_spacing_polish(html: str) -> str:
    if "data-aig-spacing-polish" in html:
        return html
    if "</body>" in html:
        return html.replace("</body>", SPACING_POLISH_PATCH + "</body>")
    return html + SPACING_POLISH_PATCH

@app.get("/", response_class=HTMLResponse)
async def dashboard(_user: str = Depends(require_auth)):
    html_path = BASE_DIR / "design" / "dashboard.html"
    if not html_path.exists():
        html_path = BASE_DIR / "dashboard.html"  # legacy fallback
    if html_path.exists():
        html = html_path.read_text(encoding="utf-8")
        html = _inject_spacing_polish(
            _inject_dashboard_integration_patch(_inject_sensor_ui_patch(html))
        )
        return _no_store(HTMLResponse(_apply_content_hashed_assets(html)))
    return _no_store(HTMLResponse("<h1>dashboard.html not found alongside main.py</h1>",
                                  status_code=404))

# ── Runtime performance defaults ──────────────────────────────────────────────
def _extract_security_cam_arg():
    """Remove --security-cam from sys.argv and return its source if provided."""
    global SECURITY_CAMERA_SOURCE
    env_source = os.getenv("SECURITY_CAMERA_SOURCE", "").strip()
    source = env_source
    explicit = bool(env_source)
    cleaned = [sys.argv[0]]
    i = 1
    while i < len(sys.argv):
        arg = sys.argv[i]
        if arg == "--security-cam":
            if i + 1 < len(sys.argv):
                source = sys.argv[i + 1]
                explicit = True
                i += 2
                continue
        elif arg.startswith("--security-cam="):
            source = arg.split("=", 1)[1]
            explicit = True
            i += 1
            continue
        cleaned.append(arg)
        i += 1
    sys.argv = cleaned
    # Auto-default to the RPi CSI camera ONLY when:
    #   1. picamera2 is available
    #   2. the user didn't pass --security-cam or set SECURITY_CAMERA_SOURCE
    #   3. FarmMonitor isn't already claiming the CSI camera (else both threads
    #      race for the same hardware and the second to start gets nothing)
    if not source and not explicit and _PICAMERA2_AVAILABLE:
        farm_uses_csi = (
            USE_RPICAM
            or (FARM_MONITOR_CAMERA or "").strip().lower()
               in ("rpi", "csi", "csi:0", "csi:1")
        )
        if not farm_uses_csi:
            source = "rpi"
    SECURITY_CAMERA_SOURCE = source
    return source


def _ensure_pipeline_perf_defaults(security_source: str = ""):
    """No-op on the CPU build. Hailo's GStreamerDetectionApp parses argv;
    we don't, so there are no flags to back-fill here."""
    return


def _start_meshtastic_bridge():
    """Start the LoRa <-> FLORA bridge inside this process when MESH_ENABLED=true.

    The bridge runs as a daemon thread. The same bridge code is used by the
    standalone meshtastic_flora_bridge.py script — here we just import it and
    drive it in-process so users don't have to run two services."""
    if str(os.getenv("MESH_ENABLED", "")).strip().lower() not in ("1", "true", "yes", "on"):
        hailo_logger.info("Meshtastic bridge disabled (set MESH_ENABLED=true in .env to enable)")
        return
    try:
        import meshtastic_flora_bridge as _mb
    except Exception as e:
        hailo_logger.warning(f"Meshtastic bridge unavailable ({e}) — install `meshtastic` + `pypubsub`")
        return

    def _runner():
        try:
            cfg = _mb.build_config()
            # Default to the local dashboard if MESH_DASHBOARD_URL wasn't set.
            if not cfg.dashboard_url:
                cfg.dashboard_url = "http://127.0.0.1:8000"
            hailo_logger.info(f"Meshtastic bridge starting → {cfg.meshtastic_host}")
            _mb.MeshtasticFloraBridge(cfg).start()
        except SystemExit:
            hailo_logger.warning("Meshtastic bridge exited (connection lost); continuing without it")
        except Exception as e:
            hailo_logger.warning(f"Meshtastic bridge crashed ({e}); continuing without it")

    threading.Thread(target=_runner, daemon=True, name="meshtastic_bridge").start()


# ── Main ───────────────────────────────────────────────────────────────────────
def main():
    security_source = _extract_security_cam_arg()
    _ensure_pipeline_perf_defaults(security_source)
    hailo_logger.info("=" * 58)
    hailo_logger.info("  AIgriculture — main.py  (CPU build)")
    hailo_logger.info(f"  Relays  : BCM {RELAY_PIN_SUMMARY}")
    hailo_logger.info(f"  ADS1115 : {'READY' if I2C_AVAILABLE else 'OFFLINE'}")
    hailo_logger.info(f"  GPIO    : {'OK' if GPIO_AVAILABLE else 'SIMULATED'}")
    hailo_logger.info(f"  Vision  : CPU YOLO (Ultralytics)")
    hailo_logger.info(f"  FarmCam : {FARM_MONITOR_CAMERA} @ {FARM_MONITOR_FPS:g} FPS")
    hailo_logger.info(f"  SecCam  : {security_source if security_source else 'disabled (use --security-cam /dev/videoX)'}")
    hailo_logger.info(f"  Storage : {STORAGE_PATH}")
    hailo_logger.info(f"  Web     : http://0.0.0.0:8000")
    hailo_logger.info("=" * 58)

    threading.Thread(target=sensor_irr_loop, daemon=True, name="sensor_irr").start()
    threading.Thread(target=_siren_loop, daemon=True, name="intruder_siren").start()
    try:
        _ensure_writable_dir(FARM_MONITOR_WORK, "Farm Monitor work folder")
    except PermissionError as _e:
        hailo_logger.warning(str(_e))
    threading.Thread(target=farm_monitor_camera_loop, daemon=True, name="farm_monitor_camera").start()
    threading.Thread(target=farm_monitor_scheduler_loop, daemon=True, name="farm_monitor_scheduler").start()

    threading.Thread(
        target=lambda: uvicorn.run(app, host="0.0.0.0", port=8000,
                                   log_level="warning", server_header=False),
        daemon=True,
        name="uvicorn",
    ).start()

    _start_meshtastic_bridge()

    if security_source:
        threading.Thread(
            target=cpu_security_camera_loop,
            args=(security_source,),
            daemon=True,
            name="security_camera",
        ).start()
    else:
        hailo_logger.info("Security camera disabled (pass --security-cam /dev/videoX to enable)")

    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        pass
    finally:
        all_relays_off()
        _buzzer_tone(False)
        if GPIO_AVAILABLE and _gpio_handle is not None:
            GPIO.gpiochip_close(_gpio_handle)


if __name__ == "__main__":
    main()
