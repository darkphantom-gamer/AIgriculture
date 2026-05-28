"""Shared runtime state.

Holds the live objects (irrigation engine, siren, cameras) and composes the
JSON the dashboard expects. Also bridges the camera threads to the async
WebSocket broadcast so a detected threat reaches the browser instantly.
"""

from __future__ import annotations

import asyncio
import json
import threading
import time
from collections import deque
from datetime import datetime
from pathlib import Path
from typing import List, Optional

from . import config
from .config import PLANTS

SIREN_HOLD_S = 8.0


class AppState:
    def __init__(self, irrigation, siren, security=None, farm_camera=None, app_config=None):
        self.irrigation = irrigation
        self.siren = siren
        self.security = security          # SecurityCamera | None
        self.farm_camera = farm_camera    # CameraSource | None (FarmMonitor preview)
        self.app_config = app_config or {}

        self.at_farm = False              # guard disarmed while the operator is on-site
        self.notification_email = ""
        # By default only A & B are "active" (visible on the dashboard); the rest
        # are dormant until enabled. Users can register new plants via the UI.
        defaults = [p for p in PLANTS if p in ("a", "b")] or PLANTS[:2]
        self.active_plants: List[str] = list(defaults)
        self.plant_names = {p: f"Plant {p.upper()}" for p in PLANTS}

        self.events: deque = deque(maxlen=200)
        self.ws_clients: list = []
        self.ws_lock = threading.Lock()
        self.loop: Optional[asyncio.AbstractEventLoop] = None

        # pluggable subsystems, attached after construction
        self.flora = None
        self.farm_monitor = None

    # ── snapshots ────────────────────────────────────────────────────────────
    def add_plant(self, plant: str, name: Optional[str] = None) -> None:
        """Register a new plant letter with a display name. Idempotent."""
        plant = plant.lower()
        if plant not in PLANTS:
            PLANTS.append(plant)
            PLANTS.sort()
        if plant not in self.plant_names:
            self.plant_names[plant] = name or f"Plant {plant.upper()}"

    def state_snapshot(self) -> dict:
        snap = self.irrigation.snapshot()
        plants = snap["plants"]
        # Source-of-truth list: whichever plants the irrigation engine knows
        # about. That way runtime-added plants show up immediately.
        all_plants = list(plants.keys())
        return {
            "type": "state",
            "active_plants": self.active_plants,
            "all_plants": all_plants,
            "plant_names": self.plant_names,
            "moisture": {p: plants[p]["moisture"] for p in all_plants},
            "sensor_status": {
                p: {"online": plants[p]["online"], "value": plants[p]["moisture"],
                    "last_error": self.irrigation.sensors.errors.get(p)}
                for p in all_plants
            },
            "pumps": {p: plants[p]["pump_on"] for p in all_plants},
            "auto_irr": snap["auto"],
            "at_farm": self.at_farm,
            "alerts": self.active_alerts(),
            "burst": self.irrigation.burst_states(),
            "last_watered": self.irrigation.last_watered(),
            "farm_monitor": self.farm_status(),
        }

    def health(self) -> dict:
        return {
            "ok": True,
            "service": "aigriculture",
            "time": datetime.now().isoformat(timespec="seconds"),
            "gpio_available": self.irrigation.relay.available,
            "i2c_available": self.irrigation.sensors.available,
            "security_camera": self.security is not None,
            "farm_camera": self.farm_camera is not None,
            "plants": len(PLANTS),
        }

    def farm_status(self) -> dict:
        if self.farm_monitor is not None:
            return self.farm_monitor.status()
        return {"state": "idle", "message": "", "last_result": None}

    def active_alerts(self) -> list:
        cutoff = time.time() - 60
        out = []
        for e in self.events:
            if e.get("event_type") == "security" and e.get("_ts", 0) >= cutoff:
                out.append({"name": e["label"], "time": e["time"], "type": "security"})
        return out

    # ── broadcast ────────────────────────────────────────────────────────────
    async def broadcast(self, data: dict) -> None:
        msg = json.dumps(data)
        with self.ws_lock:
            clients = list(self.ws_clients)
        dead = []
        for ws in clients:
            try:
                await ws.send_text(msg)
            except Exception:
                dead.append(ws)
        if dead:
            with self.ws_lock:
                for d in dead:
                    if d in self.ws_clients:
                        self.ws_clients.remove(d)

    def broadcast_threadsafe(self, data: dict) -> None:
        if self.loop is not None:
            try:
                asyncio.run_coroutine_threadsafe(self.broadcast(data), self.loop)
            except Exception:
                pass

    # ── security threat hook (called from the camera thread) ──────────────────
    def on_threat(self, detections, frame) -> None:
        if self.at_farm:
            return  # operator is on-site; guard disarmed
        self.siren.arm(True)
        threading.Timer(SIREN_HOLD_S, lambda: self.siren.arm(False)).start()

        labels = ", ".join(sorted({d.label for d in detections}))
        conf = max((d.confidence for d in detections), default=0.0)
        image = self._save_snapshot(frame)
        now = time.time()
        event = {
            "time": datetime.now().isoformat(timespec="seconds"),
            "_ts": now,
            "label": labels or "intruder",
            "conf": round(conf, 3),
            "event_type": "security",
            "image": image,
        }
        self.events.appendleft(event)
        self.broadcast_threadsafe({"type": "alert", "event": event})

    def _save_snapshot(self, frame) -> str:
        try:
            import cv2
            folder = config.STORAGE_DIR / "security"
            folder.mkdir(parents=True, exist_ok=True)
            name = f"{int(time.time()*1000)}.jpg"
            cv2.imwrite(str(folder / name), frame, [cv2.IMWRITE_JPEG_QUALITY, 80])
            return f"/storage_img/security/{name}"
        except Exception:
            return ""
