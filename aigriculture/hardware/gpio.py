"""Relays (water pumps) and the intruder siren (passive buzzers).

The actual pin numbers live in wiring.yaml (loaded by `wiring.py`) so users
never have to touch this file to match their own board.
"""

from __future__ import annotations

import threading
import time
from typing import Dict

from . import wiring

try:
    import lgpio
    _HAVE_LGPIO = True
except ImportError:
    lgpio = None  # type: ignore
    _HAVE_LGPIO = False


def _open_chip(preferred: int) -> int | None:
    """Open /dev/gpiochipN. Tries the configured chip first, then 0, then 4
    (the Pi 5 fallback). Returns the handle, or None if nothing worked.
    """
    if not _HAVE_LGPIO:
        return None
    tried: list[int] = []
    for n in (preferred, 0, 4):
        if n in tried:
            continue
        tried.append(n)
        try:
            return lgpio.gpiochip_open(n)
        except Exception:
            continue
    return None


class RelayController:
    """Drives the pump relays. A no-op when lgpio is unavailable (e.g. off-Pi)."""

    def __init__(self) -> None:
        self._pins: Dict[str, int] = wiring.relay_pins()
        active_low = wiring.relay_active_low()
        self._on_level = 0 if active_low else 1
        self._off_level = 1 if active_low else 0
        self._handle = _open_chip(wiring.gpio_chip())
        self.available = False
        if self._handle is not None:
            try:
                for pin in self._pins.values():
                    lgpio.gpio_claim_output(self._handle, pin, self._off_level)
                self.available = True
            except Exception as e:
                print(f"[WARN] relays unavailable: {e}")

    def set(self, plant: str, on: bool) -> None:
        if not self.available or plant not in self._pins:
            return
        lgpio.gpio_write(self._handle, self._pins[plant], self._on_level if on else self._off_level)

    def all_off(self) -> None:
        for plant in self._pins:
            self.set(plant, False)

    def add_pin(self, plant: str, pin: int) -> bool:
        """Register a new plant → BCM pin at runtime. Returns True on success."""
        plant = plant.lower()
        if not self._handle or not _HAVE_LGPIO:
            self._pins[plant] = int(pin)
            return False  # tracked but pin not actually claimed (off-Pi)
        try:
            lgpio.gpio_claim_output(self._handle, int(pin), self._off_level)
            self._pins[plant] = int(pin)
            return True
        except Exception as e:
            print(f"[WARN] could not claim BCM {pin} for plant {plant.upper()}: {e}")
            return False

    @property
    def pins(self) -> Dict[str, int]:
        return dict(self._pins)

    @property
    def handle(self):
        return self._handle


class Siren:
    """Dual passive buzzers, beeping in unison while armed. Runs its own thread
    so the detection pipeline is never blocked. `enabled` is the master mute."""

    def __init__(self, relay: RelayController) -> None:
        self.enabled = True
        self._sounding_wanted = False
        self._lock = threading.Lock()
        self._handle = relay.handle
        self._pins = wiring.buzzer_pins()
        self._freq = wiring.buzzer_freq_hz()
        self._on_s = wiring.buzzer_on_s()
        self._off_s = wiring.buzzer_off_s()
        self.available = False
        if _HAVE_LGPIO and self._handle is not None:
            try:
                for pin in self._pins:
                    lgpio.gpio_claim_output(self._handle, pin, 0)
                self.available = True
            except Exception as e:
                print(f"[WARN] buzzers unavailable: {e}")
        if self.available:
            threading.Thread(target=self._loop, name="siren", daemon=True).start()

    def _tone(self, on: bool) -> None:
        if not self.available:
            return
        for pin in self._pins:
            try:
                lgpio.tx_pwm(self._handle, pin, self._freq if on else 0, 50 if on else 0)
            except Exception:
                pass

    def arm(self, on: bool) -> None:
        with self._lock:
            self._sounding_wanted = bool(on)

    def test(self) -> None:
        self._tone(True)
        time.sleep(0.4)
        self._tone(False)

    def _loop(self) -> None:
        sounding = False
        while True:
            with self._lock:
                active = self._sounding_wanted and self.enabled
            try:
                if active:
                    self._tone(True);  time.sleep(self._on_s)
                    self._tone(False); time.sleep(self._off_s)
                    sounding = True
                else:
                    if sounding:
                        self._tone(False)
                        sounding = False
                    time.sleep(0.1)
            except Exception:
                self._tone(False)
                time.sleep(0.5)
