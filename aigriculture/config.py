"""Central configuration.

Loads .env and config.yaml, and exposes the tunable thresholds the irrigation
and detection logic use. The hardware wiring (pin map, ADC channels, calibration)
lives in wiring.yaml — see hardware/wiring.py.

`PLANTS` is a mutable list, populated at import time from wiring.yaml and the
runtime registry (runtime/plants.json). Code that does `for p in PLANTS:` keeps
working; new plants registered via the UI append into the same list.
"""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any, Dict, List

BASE_DIR = Path(__file__).resolve().parent.parent
RUNTIME_DIR = Path(os.getenv("AIGRI_RUNTIME", BASE_DIR / "runtime"))
STORAGE_DIR = Path(os.getenv("AIGRI_STORAGE", RUNTIME_DIR / "storage"))


def _initial_plants() -> List[str]:
    # Union of (relay pins) + (moisture channels) from wiring.yaml gives us the
    # set of plants the user has actually wired. Defaults to "abcdefgh".
    from .hardware import wiring  # local import to avoid hard cycle at import
    declared = set(wiring.relay_pins()) | set(wiring.moisture_channels())
    # Plus anything the operator added at runtime via the UI:
    persist = RUNTIME_DIR / "plants.json"
    if persist.exists():
        try:
            extra = json.loads(persist.read_text(encoding="utf-8"))
            if isinstance(extra, dict):
                declared |= {p.lower() for p in extra}
        except Exception:
            pass
    return sorted(declared) or list("abcdefgh")


PLANTS: List[str] = _initial_plants()


def _f(name: str, default: float) -> float:
    try:
        return float(os.getenv(name, default))
    except (TypeError, ValueError):
        return default


# ── Irrigation thresholds (percent moisture) ───────────────────────────────
TRIGGER_PCT = _f("AIGRI_TRIGGER_PCT", 45.0)   # auto-water starts below this
STOP_PCT = _f("AIGRI_STOP_PCT", 65.0)         # stop once moisture reaches this
LOCK_PCT = _f("AIGRI_LOCK_PCT", 70.0)         # HARD safety lock: never pump at/above this

# ── Burst-watering cadence ──────────────────────────────────────────────────
BURST_ON_S = _f("AIGRI_BURST_ON_S", 3.0)      # pump ON seconds per burst
BURST_WAIT_S = _f("AIGRI_BURST_WAIT_S", 10.0)  # soak/absorb pause between bursts
BURST_CLIMB_SKIP = _f("AIGRI_BURST_CLIMB_SKIP", 1.5)  # skip next burst if moisture rose >= this during soak
CMD_MAX_S = _f("AIGRI_CMD_MAX_S", 180.0)      # safety cap on a manual/FLORA burst session
SENSOR_POLL_S = _f("AIGRI_SENSOR_POLL_S", 0.5)

# ── Detection ───────────────────────────────────────────────────────────────
CONF_THRESH = _f("AIGRI_CONF_THRESH", 0.45)


def load_env(path: str | os.PathLike = ".env") -> None:
    """Load KEY=VALUE lines from a .env file into the environment.

    Existing environment variables win, so real deployment env always overrides
    the file. Silently does nothing if the file is absent.
    """
    p = Path(path)
    if not p.exists():
        return
    for line in p.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, val = line.partition("=")
        key = key.strip()
        if key and key not in os.environ:
            os.environ[key] = val.strip()


def load_yaml(path: str | os.PathLike = "config.yaml") -> Dict[str, Any]:
    """Load config.yaml if present; return {} otherwise."""
    p = Path(path)
    if not p.exists():
        return {}
    try:
        import yaml
        return yaml.safe_load(p.read_text(encoding="utf-8")) or {}
    except Exception:
        return {}
