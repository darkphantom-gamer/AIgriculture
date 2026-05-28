"""Soil moisture via two ADS1115 ADCs over I2C (8 capacitive sensors).

The plant-to-channel map, the I2C bus, and the dry/wet calibration values all
live in wiring.yaml — change them there, not here.
"""

from __future__ import annotations

import struct
import threading
import time
from typing import Dict, List, Optional, Tuple

from . import wiring

# ADS1115 register words for single-ended A0..A3, 128 SPS, +/-4.096 V
_REG_CONV = 0x00
_REG_CFG = 0x01
_MUX = [0xC1E3, 0xD1E3, 0xE1E3, 0xF1E3]
_CONV_WAIT_S = 0.009
_WARN_THROTTLE_S = 300.0

try:
    import smbus2
    _HAVE_I2C = True
except ImportError:
    smbus2 = None  # type: ignore
    _HAVE_I2C = False


class MoistureSensors:
    """Reads moisture percentages. Returns None for any channel that errors
    (sensor unplugged, bus missing) without raising."""

    def __init__(self) -> None:
        self._channels: Dict[str, Tuple[int, int]] = wiring.moisture_channels()
        self._dry = wiring.moisture_dry_value()
        self._wet = wiring.moisture_wet_value()
        self._bus_num = wiring.i2c_bus()
        self._bus = None
        self.available = False
        self._lock = threading.Lock()
        self._last_warn: Dict[str, float] = {p: 0.0 for p in self._channels}
        self.errors: Dict[str, Optional[str]] = {p: None for p in self._channels}
        if _HAVE_I2C:
            try:
                self._bus = smbus2.SMBus(self._bus_num)
                self.available = True
            except Exception as e:
                print(f"[WARN] I2C/ADS1115 unavailable: {e}")

    @property
    def channels(self) -> Dict[str, Tuple[int, int]]:
        return dict(self._channels)

    def read(self, plant: str) -> Optional[float]:
        if not self.available or plant not in self._channels:
            self.errors[plant] = "i2c_unavailable"
            return None
        addr, ch = self._channels[plant]
        try:
            cfg = _MUX[ch]
            with self._lock:
                self._bus.write_i2c_block_data(addr, _REG_CFG, [(cfg >> 8) & 0xFF, cfg & 0xFF])
                time.sleep(_CONV_WAIT_S)
                data = self._bus.read_i2c_block_data(addr, _REG_CONV, 2)
            raw = struct.unpack(">h", bytes(data))[0]
            if raw <= -32768 or raw >= 32767:
                self.errors[plant] = f"invalid_raw:{raw}"
                return None
            span = self._dry - self._wet
            if span == 0:
                self.errors[plant] = "bad_calibration"
                return None
            pct = (self._dry - raw) / span * 100.0
            self.errors[plant] = None
            return round(max(0.0, min(100.0, pct)), 1)
        except Exception as e:
            self.errors[plant] = str(e)
            now = time.time()
            if now - self._last_warn[plant] >= _WARN_THROTTLE_S:
                self._last_warn[plant] = now
                print(f"[WARN] moisture {plant.upper()} @0x{addr:02x} ch{ch}: {e}")
            return None

    def read_all(self) -> Dict[str, Optional[float]]:
        return {p: self.read(p) for p in self._channels}

    # ── runtime additions / scanning ─────────────────────────────────────────
    def add_channel(self, plant: str, addr: int, channel: int) -> None:
        """Register a new plant → (addr, channel) at runtime."""
        plant = plant.lower()
        self._channels[plant] = (int(addr), int(channel))
        self._last_warn.setdefault(plant, 0.0)
        self.errors.setdefault(plant, None)

    def _raw_read(self, addr: int, channel: int) -> Optional[int]:
        if not self.available or channel not in range(4):
            return None
        try:
            cfg = _MUX[channel]
            with self._lock:
                self._bus.write_i2c_block_data(addr, _REG_CFG, [(cfg >> 8) & 0xFF, cfg & 0xFF])
                time.sleep(_CONV_WAIT_S)
                data = self._bus.read_i2c_block_data(addr, _REG_CONV, 2)
            return struct.unpack(">h", bytes(data))[0]
        except Exception:
            return None

    def scan_bus(self, addresses: tuple = (0x48, 0x49, 0x4A, 0x4B)) -> List[dict]:
        """Probe every ADS1115 channel at the given addresses.

        Returns a list of `{addr, channel, raw, plausible, assigned_to}` rows,
        where `plausible` is True when the raw count suggests a sensor is
        actually wired up (i.e. the channel is not floating).
        """
        assigned = {ch: p for p, ch in self._channels.items()}
        rows: List[dict] = []
        for addr in addresses:
            for ch in range(4):
                raw = self._raw_read(addr, ch)
                # Floating channels read close to the +VDD rail (~26000-32767).
                # A capacitive probe in dry air sits ~16000-19000, in water ~7000-8500.
                # We accept anything in [3000, 22000] as "looks like a real sensor".
                plausible = raw is not None and 3000 < raw < 22000
                rows.append({
                    "addr": addr,
                    "channel": ch,
                    "raw": raw,
                    "plausible": plausible,
                    "assigned_to": assigned.get((addr, ch)),
                })
        return rows

    def unassigned_channels(self) -> List[dict]:
        """Scan, then return only channels that look wired up AND are not yet
        mapped to a plant — the candidates for "Add sensor"."""
        return [r for r in self.scan_bus() if r["plausible"] and not r["assigned_to"]]
