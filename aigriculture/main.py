"""Entry point:  python -m aigriculture [options]

Builds the hardware, cameras, detector, irrigation engine, and dashboard, then
serves it. Everything is optional and degrades gracefully — with no cameras and
no Pi hardware you still get the full dashboard (handy for trying it on a laptop).
"""

from __future__ import annotations

import argparse
import os

from . import config
from .camera.base import open_camera
from .hardware.gpio import RelayController, Siren
from .hardware.moisture import MoistureSensors
from .inference.base import build_detector
from .irrigation import IrrigationEngine
from .flora.agent import FloraAgent
from .security.camera import DEFAULT_THREAT_CLASSES, SecurityCamera
from .state import AppState
from .web.app import create_app


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser("aigriculture", description="Raspberry Pi smart-farm dashboard")
    p.add_argument("--host", default=os.getenv("AIGRI_HOST", "0.0.0.0"))
    p.add_argument("--port", type=int, default=int(os.getenv("AIGRI_PORT", "8000")))
    p.add_argument("--security-camera", default=os.getenv("SECURITY_CAMERA", ""),
                   help="csi:0 | /dev/video0 | rtsp://host/stream  (intruder detection)")
    p.add_argument("--farm-camera", default=os.getenv("FARM_CAMERA", ""),
                   help="csi:1 | /dev/video2 | rtsp://...  (disease/ripeness preview)")
    p.add_argument("--backend", default=os.getenv("AIGRI_BACKEND", "cpu"),
                   choices=["cpu", "hailo"], help="detection backend (default: cpu)")
    p.add_argument("--model", default=os.getenv("AIGRI_MODEL", "yolo11n.pt"),
                   help="YOLO weights for the security camera")
    p.add_argument("--imgsz", type=int, default=int(os.getenv("AIGRI_IMGSZ", "480")))
    p.add_argument("--detect-every", type=int, default=int(os.getenv("AIGRI_DETECT_EVERY", "3")))
    p.add_argument("--disease-model", default=os.getenv("DISEASE_MODEL", "models/Disease_detect.pt"))
    p.add_argument("--ripeness-model", default=os.getenv("RIPENESS_MODEL", "models/Ripeness_detect.pt"))
    return p.parse_args()


def _apply_runtime_registry(sensors, relay, irrigation, state) -> None:
    """Apply the UI-added plants from runtime/plants.json to live hardware."""
    import json
    path = config.RUNTIME_DIR / "plants.json"
    if not path.exists():
        return
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except Exception as e:
        print(f"[WARN] could not read {path}: {e}")
        return
    if not isinstance(data, dict):
        return
    for plant, entry in data.items():
        plant = str(plant).lower()
        moist = (entry or {}).get("moisture") or {}
        if moist.get("addr") is not None and moist.get("channel") is not None:
            sensors.add_channel(plant, int(moist["addr"]), int(moist["channel"]))
        relay_pin = (entry or {}).get("relay_pin")
        if relay_pin is not None:
            relay.add_pin(plant, int(relay_pin))
        irrigation.add_plant(plant)
        state.add_plant(plant, (entry or {}).get("name"))


def main() -> None:
    config.load_env(".env")
    args = parse_args()

    relay = RelayController()
    siren = Siren(relay)
    sensors = MoistureSensors()
    irrigation = IrrigationEngine(relay, sensors)
    # Build dicts for the full set of plants declared in wiring + runtime registry.
    for plant in config.PLANTS:
        irrigation.add_plant(plant)
    state = AppState(irrigation, siren, app_config=config.load_yaml("config.yaml"))
    # Hot-attach any sensors/relays declared in runtime/plants.json (UI-added).
    _apply_runtime_registry(sensors, relay, irrigation, state)
    irrigation.on_burst = lambda plant: state.broadcast_threadsafe({"type": "irrigation", "plant": plant})
    state.flora = FloraAgent(state)  # works offline; cloud chat activates when an API key is set

    if os.getenv("MESH_ENABLED", "false").lower() == "true":
        from .mesh.meshtastic import MeshBridge
        allowed = [n for n in os.getenv("MESH_ALLOWED_NODES", "").split(",") if n.strip()]
        MeshBridge(state, host=os.getenv("MESH_HOST", "localhost"),
                   allowed_nodes=allowed or None,
                   reply_max_chars=int(os.getenv("MESH_REPLY_MAX_CHARS", "200"))).start()
        print("[INFO] Meshtastic bridge enabled")

    if args.security_camera:
        try:
            cam = open_camera(args.security_camera, width=640, height=480, fps=15)
            detector = build_detector(args.backend, model_path=args.model,
                                      conf_threshold=config.CONF_THRESH,
                                      classes=DEFAULT_THREAT_CLASSES, imgsz=args.imgsz)
            state.security = SecurityCamera(cam, detector, detect_every=args.detect_every,
                                            on_threat=state.on_threat)
            print(f"[INFO] security camera on {args.security_camera} ({args.backend})")
        except Exception as e:
            print(f"[WARN] security camera disabled: {e}")

    if args.farm_camera:
        try:
            state.farm_camera = open_camera(args.farm_camera, width=640, height=480, fps=10)
            print(f"[INFO] farm camera on {args.farm_camera}")
            from .farmmonitor.scan import FarmMonitor
            fm = FarmMonitor(state, state.farm_camera, args.disease_model, args.ripeness_model,
                             state.app_config, conf=config.CONF_THRESH)
            state.farm_monitor = fm
            fm.start()
            print(f"[INFO] FarmMonitor {'enabled' if fm.enabled else 'idle (no models)'}")
        except Exception as e:
            print(f"[WARN] farm camera disabled: {e}")

    app = create_app(state)
    import uvicorn
    uvicorn.run(app, host=args.host, port=args.port, log_level="info")


if __name__ == "__main__":
    main()
