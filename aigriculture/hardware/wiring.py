"""Hardware wiring map — loaded once from wiring.yaml.

Users edit `wiring.yaml` at the repo root (or mount one into the container) to
match their own board.  This module is the SINGLE place the rest of the code
asks "which BCM pin is plant A's relay?" or "what ADC channel reads plant E?",
so changing your wiring never means editing Python.

If wiring.yaml is absent, sane defaults from the reference build are used.
"""

from __future__ import annotations

import os
from pathlib import Path
from typing import Any, Dict, List, Tuple

# ── built-in defaults (match aigriculture.txt) ─────────────────────────────
_DEFAULTS: Dict[str, Any] = {
    "gpio": {"chip": 0},
    "relays": {
        "active_low": True,
        "pins": {"a": 17, "b": 27, "c": 22, "d": 23,
                 "e": 5, "f": 6, "g": 13, "h": 19},
    },
    "buzzers": {
        "pins": [18, 12],
        "freq_hz": 2700,
        "on_s": 0.25,
        "off_s": 0.20,
    },
    "moisture": {
        "bus": 1,
        "dry_value": 17408,
        "wet_value": 7569,
        "channels": {
            "a": [0x48, 0], "b": [0x48, 1], "c": [0x48, 2], "d": [0x48, 3],
            "e": [0x49, 0], "f": [0x49, 1], "g": [0x49, 2], "h": [0x49, 3],
        },
    },
}


def _merge(base: Dict[str, Any], override: Dict[str, Any]) -> Dict[str, Any]:
    out = dict(base)
    for k, v in (override or {}).items():
        if isinstance(v, dict) and isinstance(out.get(k), dict):
            out[k] = _merge(out[k], v)
        else:
            out[k] = v
    return out


def _load_yaml(path: Path) -> Dict[str, Any]:
    if not path.exists():
        return {}
    try:
        import yaml
        return yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    except Exception as e:
        print(f"[WARN] could not read {path}: {e} — using built-in wiring defaults")
        return {}


def _find_wiring_file() -> Path:
    """Look for wiring.yaml beside the project, then in CWD, then env override."""
    env = os.getenv("WIRING_FILE", "").strip()
    if env:
        return Path(env)
    here = Path(__file__).resolve().parent.parent.parent  # repo root
    for cand in (here / "wiring.yaml", Path.cwd() / "wiring.yaml"):
        if cand.exists():
            return cand
    return here / "wiring.yaml"  # may not exist; defaults will apply


_CONFIG = _merge(_DEFAULTS, _load_yaml(_find_wiring_file()))


# ── public API (typed accessors) ───────────────────────────────────────────
def gpio_chip() -> int:
    return int(_CONFIG["gpio"]["chip"])


def relay_active_low() -> bool:
    return bool(_CONFIG["relays"]["active_low"])


def relay_pins() -> Dict[str, int]:
    return {k.lower(): int(v) for k, v in _CONFIG["relays"]["pins"].items()}


def buzzer_pins() -> List[int]:
    return [int(p) for p in _CONFIG["buzzers"]["pins"]]


def buzzer_freq_hz() -> int:
    return int(_CONFIG["buzzers"]["freq_hz"])


def buzzer_on_s() -> float:
    return float(_CONFIG["buzzers"]["on_s"])


def buzzer_off_s() -> float:
    return float(_CONFIG["buzzers"]["off_s"])


def i2c_bus() -> int:
    return int(_CONFIG["moisture"]["bus"])


def moisture_dry_value() -> int:
    return int(_CONFIG["moisture"]["dry_value"])


def moisture_wet_value() -> int:
    return int(_CONFIG["moisture"]["wet_value"])


def moisture_channels() -> Dict[str, Tuple[int, int]]:
    out: Dict[str, Tuple[int, int]] = {}
    for plant, pair in _CONFIG["moisture"]["channels"].items():
        addr, ch = pair
        out[plant.lower()] = (int(addr), int(ch))
    return out
