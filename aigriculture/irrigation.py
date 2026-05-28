"""Auto-irrigation engine.

Drives a 3s-ON / 10s-soak burst cycle per plant with three safety gates:

    TRIGGER_PCT (45%)  auto-watering starts below this
    STOP_PCT    (65%)  stop once moisture reaches this
    LOCK_PCT    (70%)  HARD lock — no pump ever runs at/above this, period

Manual / FLORA "commanded" bursts are time-boxed (CMD_MAX_S) so a blind burst
with an offline sensor can never run forever.
"""

from __future__ import annotations

import threading
import time
from collections import deque
from typing import Callable, Deque, Dict, Optional

from . import config
from .config import PLANTS
from .hardware.gpio import RelayController
from .hardware.moisture import MoistureSensors

EventHook = Callable[[str], None]


class IrrigationEngine:
    def __init__(
        self,
        relay: RelayController,
        sensors: MoistureSensors,
        on_burst: Optional[EventHook] = None,
    ):
        self.relay = relay
        self.sensors = sensors
        self.on_burst = on_burst

        self.auto_enabled = True
        self._lock = threading.Lock()
        self._thread: Optional[threading.Thread] = None
        self._stop_evt = threading.Event()

        self.moisture: Dict[str, Optional[float]] = {p: None for p in PLANTS}
        self.pump_on: Dict[str, bool] = {p: False for p in PLANTS}
        self.commanded: Dict[str, bool] = {p: False for p in PLANTS}
        self._state: Dict[str, str] = {p: "idle" for p in PLANTS}
        self._timer: Dict[str, float] = {p: 0.0 for p in PLANTS}
        self._ref: Dict[str, Optional[float]] = {p: None for p in PLANTS}
        self._deadline: Dict[str, float] = {p: 0.0 for p in PLANTS}
        self.history: Dict[str, Deque[dict]] = {p: deque(maxlen=8640) for p in PLANTS}

    # ── runtime plant registration ──────────────────────────────────────────
    def add_plant(self, plant: str) -> None:
        """Register a new plant in the engine. Safe to call after start()."""
        plant = plant.lower()
        with self._lock:
            if plant in self.moisture:
                return
            self.moisture[plant] = None
            self.pump_on[plant] = False
            self.commanded[plant] = False
            self._state[plant] = "idle"
            self._timer[plant] = 0.0
            self._ref[plant] = None
            self._deadline[plant] = 0.0
            self.history[plant] = deque(maxlen=8640)

    # ── lifecycle ────────────────────────────────────────────────────────────
    def start(self) -> None:
        if self._thread and self._thread.is_alive():
            return
        self._stop_evt.clear()
        self._thread = threading.Thread(target=self._loop, name="irrigation", daemon=True)
        self._thread.start()

    def stop(self) -> None:
        self._stop_evt.set()
        self.relay.all_off()

    # ── public controls ────────────────────────────────────────────────────
    def set_auto(self, on: bool) -> None:
        with self._lock:
            self.auto_enabled = bool(on)

    def command_burst(self, plant: str, on: bool = True) -> None:
        """Start (on=True) or stop a manual/FLORA burst for one plant."""
        if plant not in self.moisture:
            return
        if on:
            self.commanded[plant] = True
        else:
            self._stop_plant(plant)

    def snapshot(self) -> dict:
        with self._lock:
            return {
                "auto": self.auto_enabled,
                "plants": {
                    p: {
                        "moisture": self.moisture[p],
                        "pump_on": self.pump_on[p],
                        "commanded": self.commanded[p],
                        "online": self.sensors.errors.get(p) is None and self.moisture[p] is not None,
                    }
                    for p in list(self.moisture.keys())
                },
            }

    def burst_states(self) -> Dict[str, str]:
        with self._lock:
            return dict(self._state)

    def last_watered(self) -> Dict[str, float]:
        out: Dict[str, float] = {}
        for p in list(self.history.keys()):
            last = 0.0
            for e in reversed(self.history[p]):
                if e.get("event") == "burst":
                    last = e["t"]
                    break
            out[p] = last
        return out

    def moisture_history(self, limit: int = 288) -> Dict[str, list]:
        out: Dict[str, list] = {}
        for p in list(self.history.keys()):
            pts = [e for e in self.history[p] if "v" in e][-limit:]
            out[p] = [{"t": int(e["t"]), "v": e["v"]} for e in pts]
        return out

    # ── internals ────────────────────────────────────────────────────────────
    def _stop_plant(self, plant: str) -> None:
        self.relay.set(plant, False)
        with self._lock:
            self.pump_on[plant] = False
        self.commanded[plant] = False
        self._state[plant] = "idle"
        self._deadline[plant] = 0.0

    def _pump(self, plant: str, on: bool, now: float) -> None:
        self.relay.set(plant, on)
        with self._lock:
            self.pump_on[plant] = on
        if on:
            self.history[plant].append({"t": now, "event": "burst"})
            if self.on_burst:
                try:
                    self.on_burst(plant)
                except Exception:
                    pass

    def _drive_burst(self, plant: str, mv: Optional[float], now: float) -> None:
        """Advance the 3s-ON / 10s-soak cycle for one plant."""
        state = self._state[plant]
        if state == "idle":
            self._state[plant] = "burst_on"
            self._timer[plant] = now + config.BURST_ON_S
            self._pump(plant, True, now)
        elif state == "burst_on":
            if now >= self._timer[plant]:
                self._state[plant] = "burst_wait"
                self._timer[plant] = now + config.BURST_WAIT_S
                self._ref[plant] = mv
                self._pump(plant, False, now)
        elif state == "burst_wait":
            if now >= self._timer[plant]:
                ref = self._ref[plant]
                if mv is not None and ref is not None and mv - ref >= config.BURST_CLIMB_SKIP:
                    # Soil still drinking — moisture rising on its own; skip a burst.
                    self._timer[plant] = now + config.BURST_WAIT_S
                    self._ref[plant] = mv
                else:
                    self._state[plant] = "burst_on"
                    self._timer[plant] = now + config.BURST_ON_S
                    self._pump(plant, True, now)

    def _tick(self, now: float) -> None:
        readings = self.sensors.read_all()
        # Iterate over the engine's own registry, not config.PLANTS — that lets
        # new plants registered via add_plant() (UI "Add sensors") tick from the
        # next loop without a process restart.
        plants = list(self.moisture.keys())
        for plant in plants:
            mv = readings.get(plant)
            with self._lock:
                self.moisture[plant] = mv
            if mv is not None and (not self.history[plant] or now - self.history[plant][-1]["t"] >= 10):
                self.history[plant].append({"t": now, "v": mv})

        with self._lock:
            auto_on = self.auto_enabled

        for plant in plants:
            mv = self.moisture[plant]
            commanded = self.commanded[plant]
            state = self._state[plant]

            # Time-box any commanded session.
            if commanded and not self._deadline[plant]:
                self._deadline[plant] = now + config.CMD_MAX_S
            if commanded and now >= self._deadline[plant]:
                self._stop_plant(plant)
                continue

            # Sensor offline: auto can't run blind, but a commanded burst may (time-boxed).
            if mv is None:
                if not commanded:
                    if state != "idle":
                        self._stop_plant(plant)
                    continue
                self._drive_burst(plant, None, now)
                continue

            # HARD LOCK — absolute, beats everything.
            if mv >= config.LOCK_PCT and (state != "idle" or commanded):
                self._stop_plant(plant)
                continue
            # Target reached.
            if mv >= config.STOP_PCT and (state != "idle" or commanded):
                self._stop_plant(plant)
                continue

            want = commanded or (auto_on and (state != "idle" or mv < config.TRIGGER_PCT))
            if not want:
                if state != "idle":
                    self._stop_plant(plant)
                continue
            self._drive_burst(plant, mv, now)

    def _loop(self) -> None:
        while not self._stop_evt.is_set():
            try:
                self._tick(time.time())
                time.sleep(max(0.1, config.SENSOR_POLL_S))
            except Exception as e:
                print(f"[CRITICAL] irrigation loop crashed: {e}", flush=True)
                try:
                    self.relay.all_off()
                except Exception:
                    pass
                time.sleep(5.0)
