"""FLORA tools — the real farm actions FLORA can take.

Each tool reads or writes the LIVE AppState (same state the dashboard uses) and
returns a short human-readable string. The cloud agent rephrases these warmly;
offline mode returns them with a light touch.
"""

from __future__ import annotations

import json
from typing import List

from .. import config as appcfg
from ..config import PLANTS


def _norm_plant(plant: str):
    p = (plant or "").strip().lower()[:1]
    return p if p in PLANTS else None


class FloraTools:
    def __init__(self, state):
        self.state = state

    # ── read ──────────────────────────────────────────────────────────────────
    def get_farm_status(self) -> str:
        snap = self.state.irrigation.snapshot()
        active = self.state.active_plants
        lines = []
        for p in active:
            d = snap["plants"][p]
            mv = "offline" if d["moisture"] is None else f"{d['moisture']:.0f}%"
            pump = "watering" if d["pump_on"] else "idle"
            lines.append(f"Plant {p.upper()}: {mv}, {pump}")
        alerts = self.state.active_alerts()
        return json.dumps({
            "auto_irrigation": snap["auto"],
            "at_farm": self.state.at_farm,
            "plants": lines,
            "active_alerts": [a["name"] for a in alerts],
        })

    def get_moisture(self, plant: str = "") -> str:
        snap = self.state.irrigation.snapshot()["plants"]
        p = _norm_plant(plant)
        if p:
            v = snap[p]["moisture"]
            return f"Plant {p.upper()} moisture: " + ("sensor offline" if v is None else f"{v:.0f}%")
        parts = [f"{q.upper()}={'--' if snap[q]['moisture'] is None else round(snap[q]['moisture'])}"
                 for q in self.state.active_plants]
        return "Moisture — " + ", ".join(parts)

    def get_auto_irrigation(self) -> str:
        return f"Auto-irrigation is {'ON' if self.state.irrigation.auto_enabled else 'OFF'}."

    def get_camera_status(self, camera: str = "all") -> str:
        sec = "running" if self.state.security else "not configured"
        farm = "available" if self.state.farm_camera else "not configured"
        return f"Security camera: {sec}. FarmMonitor camera: {farm}."

    def get_analytics(self, hours: int = 24) -> str:
        events = list(self.state.events)
        return json.dumps({"events_total": len(events),
                           "moisture_current": self.state.state_snapshot()["moisture"]})

    def get_recent_events(self, event_type: str = "") -> str:
        evs = [e for e in self.state.events if not event_type or e.get("event_type") == event_type]
        if not evs:
            return "No recent events recorded."
        return json.dumps([{"time": e["time"], "label": e["label"], "type": e["event_type"]} for e in evs[:10]])

    # ── write ─────────────────────────────────────────────────────────────────
    def irrigate_plant(self, plant: str = "") -> str:
        p = _norm_plant(plant)
        if not p:
            return "Please name a valid plant (A-H)."
        d = self.state.irrigation.snapshot()["plants"][p]
        if d["online"] and d["moisture"] is not None and d["moisture"] >= appcfg.LOCK_PCT:
            return f"Plant {p.upper()} is at {d['moisture']:.0f}% — already moist (hardlock at {appcfg.LOCK_PCT:.0f}%), so I won't water it."
        self.state.irrigation.command_burst(p, True)
        return f"Started a gentle burst watering cycle for Plant {p.upper()}."

    def stop_pump(self, plant: str = "") -> str:
        p = _norm_plant(plant)
        if not p:
            return "Please name a valid plant (A-H)."
        self.state.irrigation.command_burst(p, False)
        return f"Stopped Plant {p.upper()}'s pump."

    def set_auto_irrigation(self, enabled: bool = True) -> str:
        self.state.irrigation.set_auto(bool(enabled))
        return f"Auto-irrigation switched {'ON' if enabled else 'OFF'}."

    def set_farm_presence(self, at_farm: bool = True) -> str:
        self.state.at_farm = bool(at_farm)
        if self.state.at_farm:
            self.state.siren.arm(False)
        return "Guard is now OFF (you're at the farm)." if at_farm else "Guard is ON (away mode)."

    def set_siren(self, enabled: bool = True) -> str:
        self.state.siren.enabled = bool(enabled)
        if not enabled:
            self.state.siren.arm(False)
        return f"Siren {'enabled' if enabled else 'muted'}."

    def trigger_farm_scan(self) -> str:
        if self.state.farm_monitor is None:
            return "FarmMonitor isn't enabled on this install."
        self.state.farm_monitor.request_scan()
        return "Queued a FarmMonitor disease/ripeness scan."

    # ── dispatch ────────────────────────────────────────────────────────────
    def execute(self, name: str, args: dict) -> str:
        fn = getattr(self, name, None)
        if not callable(fn) or name.startswith("_"):
            return f"Unknown tool: {name}"
        try:
            return fn(**(args or {}))
        except TypeError:
            return fn()
        except Exception as e:
            return f"Tool {name} failed: {e}"


def _spec(name: str, desc: str, props: dict | None = None, required: List[str] | None = None) -> dict:
    return {"type": "function", "function": {
        "name": name, "description": desc,
        "parameters": {"type": "object", "properties": props or {}, "required": required or []},
    }}

_PLANT = {"plant": {"type": "string", "description": "plant letter A-H"}}

TOOL_SPECS = [
    _spec("get_farm_status", "Overall farm status: moisture, pumps, auto mode, alerts."),
    _spec("get_moisture", "Soil moisture for one plant or all.", _PLANT),
    _spec("get_auto_irrigation", "Whether automatic irrigation is on."),
    _spec("get_camera_status", "Security and FarmMonitor camera status."),
    _spec("get_analytics", "Recent activity counts and current moisture.",
          {"hours": {"type": "integer"}}),
    _spec("get_recent_events", "Recent stored events (e.g. security).",
          {"event_type": {"type": "string"}}),
    _spec("irrigate_plant", "Start a burst watering cycle for a plant.", _PLANT, ["plant"]),
    _spec("stop_pump", "Stop a plant's pump.", _PLANT, ["plant"]),
    _spec("set_auto_irrigation", "Enable or disable automatic irrigation.",
          {"enabled": {"type": "boolean"}}, ["enabled"]),
    _spec("set_farm_presence", "Set away/guard mode (at_farm true = guard off).",
          {"at_farm": {"type": "boolean"}}, ["at_farm"]),
    _spec("set_siren", "Mute or enable the intruder siren.",
          {"enabled": {"type": "boolean"}}, ["enabled"]),
    _spec("trigger_farm_scan", "Run a FarmMonitor disease/ripeness scan now."),
]
