"""FLORA tool layer — exposes farm state and actions to the AI assistant.

State is shared by reference from main.py via init_shared_state(), so this
module does not import main and there is no circular dependency. Pump tools
go through the same lock + burst state machine + 70% hardlock as the
dashboard's water button — FLORA can never bypass those guards.
"""
import json
import time
from datetime import datetime, timedelta
from pathlib import Path

# ── Shared-state bridge ─────────────────────────────────────────────────────────
# Populated once by main.py at startup. Keys are documented in
# init_shared_state(). Dicts/lists are passed by reference (live), scalars that
# change at runtime (auto_enabled, at_farm) are reached via getter/setter calls.
_B: dict = {}


def init_shared_state(bridge: dict) -> None:
    """Inject live shared state from main.py. Called once before clients connect."""
    _B.clear()
    _B.update(bridge)


def is_ready() -> bool:
    return bool(_B)


# ── Internal helpers ────────────────────────────────────────────────────────────

def _plants():
    """Iterate only the plants the operator actually has wired/registered.

    ACTIVE_PLANTS is the authoritative list at runtime — it shrinks/grows
    when the operator removes or adds sensors via the dashboard. Falls back
    to PLANTS (max-capacity list) only if the bridge predates the
    ACTIVE_PLANTS field, which avoids reporting on plant slots the
    operator does not actually own.
    """
    return _B.get("ACTIVE_PLANTS") or _B.get("PLANTS", "abcdefgh")


def _norm_plant(plant: str):
    """Return canonical lowercase plant id, or None if invalid."""
    p = (plant or "").strip().lower()
    if p.startswith("plant"):
        p = p[5:].strip()
    return p if p in _plants() else None


def _moisture(p: str):
    with _B["moisture_lock"]:
        return _B["moisture_vals"].get(p)


def _sensor_online(p: str) -> bool:
    with _B["sensor_lock"]:
        return bool(_B["sensor_status"].get(p, {}).get("online"))


def _ok(payload) -> str:
    """Serialise a structured result for the model."""
    if isinstance(payload, str):
        return payload
    return json.dumps(payload, indent=2, default=str)


# ════════════════════════════════════════════════════════════════════════════════
# TOOL 1 — get_farm_status
# ════════════════════════════════════════════════════════════════════════════════

def get_farm_status() -> str:
    """Whole-farm overview: moisture & pumps for every active plant, security/
    intruder status, the FarmMonitor camera's plant-health & harvest read-out,
    plus a short analysed summary of everything."""
    plants = {}
    low, offline, wet, pumping = [], [], [], []
    for p in _plants():
        mv = _moisture(p)
        online = _sensor_online(p)
        with _B["pump_lock"]:
            pump_on = bool(_B["pump_states"].get(p, False))
            burst = _B["burst_state"].get(p, "idle")
        plants[p.upper()] = {
            "moisture_pct": round(mv, 1) if mv is not None else None,
            "sensor": "online" if online else "OFFLINE",
            "pump": "ON" if pump_on else "off",
            "burst": burst,
        }
        if not online or mv is None:
            offline.append(p.upper())
        elif mv < _B["TRIGGER_PCT"]:
            low.append(p.upper())
        elif mv >= _B["STOP_PCT"]:
            wet.append(p.upper())
        if pump_on:
            pumping.append(p.upper())

    alerts = list(_B["active_alerts"])
    guard_on = not _B["get_at_farm"]()
    try:
        cams = _B["camera_status"]() or {}
    except Exception:
        cams = {}
    security_cam = cams.get("security", {}) or {}
    farm_monitor = cams.get("farmmonitor", {}) or {}

    # ── short analysed overview ──
    bits = []
    if offline:
        bits.append(f"{len(offline)} sensor(s) offline ({', '.join(offline)})")
    if low:
        bits.append(f"{len(low)} plant(s) need water ({', '.join(low)})")
    if pumping:
        bits.append(f"pump running for {', '.join(pumping)}")
    if not low and not offline:
        bits.append("all plants comfortably watered")
    if alerts:
        bits.append(f"⚠ {len(alerts)} security alert(s) — intruder activity")
    else:
        bits.append("no intruders, farm secure" if guard_on
                    else "owner on-site, guard off")
    fm_result = farm_monitor.get("last_result")
    if fm_result:
        bits.append(f"FarmMonitor: {fm_result}")
    elif farm_monitor.get("scan_state"):
        bits.append(f"FarmMonitor {farm_monitor.get('scan_state')}")
    summary = "; ".join(str(b) for b in bits) + "."

    return _ok({
        "summary": summary,
        "plants": plants,
        "moisture_overview": {
            "need_water": low or "none",
            "well_watered": wet or "none",
            "sensors_offline": offline or "none",
            "pumps_running": pumping or "none",
        },
        "security": {
            "guard": "ON — away mode" if guard_on else "OFF — owner at farm",
            "intruders": alerts or "none — farm is secure",
            "camera": security_cam,
        },
        "farm_monitor": {
            "camera_online": farm_monitor.get("online"),
            "scan_state": farm_monitor.get("scan_state"),
            "plant_health_and_harvest": fm_result or "no scan result yet",
            "next_scan_at": farm_monitor.get("next_scan_at"),
        },
        "auto_irrigation": "enabled" if _B["get_auto"]() else "disabled",
        "thresholds_pct": {
            "auto_start_below": _B["TRIGGER_PCT"],
            "auto_stop_at": _B["STOP_PCT"],
            "hardlock_at": _B["LOCK_PCT"],
        },
        "timestamp": datetime.now().isoformat(timespec="seconds"),
    })


# ════════════════════════════════════════════════════════════════════════════════
# TOOL 2 — get_moisture
# ════════════════════════════════════════════════════════════════════════════════

def get_moisture(plant: str = "") -> str:
    """Moisture for one plant (A-H) or all eight when plant is empty."""
    if plant:
        p = _norm_plant(plant)
        if not p:
            return f"Invalid plant '{plant}'. Valid plants are A-H."
        targets = [p]
    else:
        targets = list(_plants())

    out = {}
    for p in targets:
        mv = _moisture(p)
        if not _sensor_online(p) or mv is None:
            with _B["sensor_lock"]:
                st = _B["sensor_status"].get(p, {})
            last_ok = st.get("last_ok")
            out[p.upper()] = (
                f"OFFLINE — sensor fault"
                + (f" (last good reading at {last_ok})" if last_ok else "")
            )
        else:
            if mv < _B["TRIGGER_PCT"]:
                label = "LOW — needs water"
            elif mv >= _B["LOCK_PCT"]:
                label = "HIGH — hardlocked, do not water"
            elif mv >= _B["STOP_PCT"]:
                label = "well watered"
            else:
                label = "OK"
            out[p.upper()] = f"{mv:.1f}% [{label}]"
    return _ok(out)


# ════════════════════════════════════════════════════════════════════════════════
# TOOL 3 — irrigate_plant   (mirrors POST /api/pump/{plant}/on)
# ════════════════════════════════════════════════════════════════════════════════

def irrigate_plant(plant: str = "") -> str:
    """Start a burst-irrigation session for a plant — mirrors the dashboard water
    button: 3s on / 10s soak, re-check, repeat until STOP_PCT, with the 70%
    hardlock as the absolute ceiling. Refused only when an online sensor already
    reads at/above the hardlock; offline sensors get a safe, time-boxed blind cycle."""
    p = _norm_plant(plant)
    if not p:
        return f"Invalid plant '{plant}'. Valid plants are A-H."

    mv = _moisture(p)
    online = _sensor_online(p)
    if online and mv is not None and mv >= _B["LOCK_PCT"]:
        return (f"Cannot water Plant {p.upper()}: moisture is {mv:.1f}%, at/above the "
                f"{_B['LOCK_PCT']:.0f}% hardlock. The soil is already wet enough.")

    # Hand the session to the irrigation loop, which drives the identical
    # 3s-ON / 10s-soak burst cycle and stops at STOP_PCT / the hardlock.
    with _B["pump_lock"]:
        _B["burst_state"][p] = "idle"
        _B["manual_pumps"][p] = True
    if "cmd_deadline" in _B:
        _B["cmd_deadline"][p] = time.time() + _B.get("CMD_MAX_S", 180.0)

    stop_at = _B["STOP_PCT"]
    if online and mv is not None:
        return (f"💧 Watering Plant {p.upper()} now (moisture {mv:.1f}%). I'll pulse "
                f"3s on / 10s soak and re-check, stopping at {stop_at:.0f}% — the "
                f"{_B['LOCK_PCT']:.0f}% hardlock always wins.")
    return (f"💧 Watering Plant {p.upper()} in safe bursts. Its sensor is offline, so "
            f"I'm running a time-boxed blind cycle (max {int(_B.get('CMD_MAX_S', 180))}s) "
            f"and will stop the instant a reading reaches {stop_at:.0f}%.")


# ════════════════════════════════════════════════════════════════════════════════
# TOOL 4 — stop_pump   (mirrors POST /api/pump/{plant}/off)
# ════════════════════════════════════════════════════════════════════════════════

def stop_pump(plant: str = "") -> str:
    """Stop the pump for a plant immediately."""
    p = _norm_plant(plant)
    if not p:
        return f"Invalid plant '{plant}'. Valid plants are A-H."

    _B["set_relay"](p, False)
    with _B["pump_lock"]:
        _B["pump_states"][p] = False
        _B["burst_state"][p] = "idle"
        _B["manual_pumps"][p] = False
    if "cmd_deadline" in _B:
        _B["cmd_deadline"][p] = 0.0
    return f"Pump OFF for Plant {p.upper()}."


# ════════════════════════════════════════════════════════════════════════════════
# TOOL 5 — get_camera_status
# ════════════════════════════════════════════════════════════════════════════════

def get_camera_status(camera: str = "all") -> str:
    """Live status of the Security camera and the FarmMonitor camera."""
    snap = _B["camera_status"]()
    cam = (camera or "all").strip().lower()
    if cam in ("security", "sec", "rpi"):
        return _ok({"security": snap.get("security")})
    if cam in ("farmmonitor", "farm", "monitor", "usb"):
        return _ok({"farmmonitor": snap.get("farmmonitor")})
    return _ok(snap)


# ════════════════════════════════════════════════════════════════════════════════
# TOOL 6 — analyze_farm
# ════════════════════════════════════════════════════════════════════════════════

_PERIOD_SECONDS = {
    "10m": 600, "15m": 900, "30m": 1800,
    "1h": 3600, "2h": 7200, "3h": 10800, "6h": 21600,
    "12h": 43200, "24h": 86400, "1d": 86400,
}


def analyze_farm(period: str = "1h") -> str:
    """Narrative analysis of moisture trend, detections and irrigation over a window."""
    window = _PERIOD_SECONDS.get((period or "1h").strip().lower(), 3600)
    cutoff = time.time() - window

    moisture_trend = {}
    with _B["hist_lock"]:
        for p in _plants():
            pts = [e["v"] for e in _B["moisture_hist"].get(p, []) if e["t"] >= cutoff]
            if pts:
                moisture_trend[p.upper()] = {
                    "avg": round(sum(pts) / len(pts), 1),
                    "min": round(min(pts), 1),
                    "max": round(max(pts), 1),
                    "samples": len(pts),
                }
        detections = [d for d in _B["detect_hist"] if d.get("t", 0) >= cutoff]
        irrigations = [e for e in _B["irr_hist"] if e.get("t", 0) >= cutoff]

    detect_counts = {}
    for d in detections:
        label = d.get("label", "unknown")
        if label not in ("No Sustained Event",):
            detect_counts[label] = detect_counts.get(label, 0) + 1

    irr_counts = {}
    for e in irrigations:
        pl = e.get("plant", "?").upper()
        irr_counts[pl] = irr_counts.get(pl, 0) + 1

    dry = [p for p, t in moisture_trend.items() if t["avg"] < _B["TRIGGER_PCT"]]
    return _ok({
        "period": period,
        "moisture_trend": moisture_trend or "no samples in window",
        "plants_below_trigger": dry or "none",
        "detections": detect_counts or "none",
        "irrigation_events": irr_counts or "none",
    })


# ════════════════════════════════════════════════════════════════════════════════
# TOOL 7 — get_storage_events
# ════════════════════════════════════════════════════════════════════════════════

def _resolve_date(date_str: str):
    s = (date_str or "today").strip().lower()
    today = datetime.now()
    if s in ("today", ""):
        return today
    if s == "yesterday":
        return today - timedelta(days=1)
    for fmt in ("%Y-%m-%d", "%Y/%m/%d", "%d-%m-%Y"):
        try:
            return datetime.strptime(s, fmt)
        except ValueError:
            continue
    return None


def _parse_event_time(meta: dict, folder: Path):
    raw = str(meta.get("time") or "")
    for fmt in ("%Y-%m-%dT%H:%M:%S.%f", "%Y-%m-%dT%H:%M:%S"):
        try:
            return datetime.strptime(raw, fmt)
        except ValueError:
            pass
    try:
        day = folder.parent
        return datetime.strptime(
            f"{day.parent.parent.name}-{day.parent.name}-{day.name} {folder.name}",
            "%Y-%m-%d %H-%M-%S",
        )
    except Exception:
        return None


def _normalise_event_type(meta: dict) -> str:
    etype = str(meta.get("event_type") or "").strip().lower()
    if etype:
        return etype
    label = str(meta.get("label") or "").lower()
    if "security camera" in label or label in {"person", "bird", "dog", "cat"}:
        return "security"
    if "harvest" in label or "ripe" in label or "flower" in label:
        return "ripeness"
    if "health" in label or "disease" in label or "mold" in label or "spot" in label or "rot" in label:
        return "disease"
    return "unknown"


def _event_matches(etype: str, wanted: str) -> bool:
    wanted = (wanted or "").strip().lower()
    if not wanted:
        return True
    aliases = {
        "farmmonitor": {"disease", "ripeness", "disease_and_ripeness"},
        "plant": {"disease", "ripeness", "disease_and_ripeness"},
        "planthealth": {"disease"},
        "health": {"disease"},
        "harvest": {"ripeness", "disease_and_ripeness"},
        "ripe": {"ripeness", "disease_and_ripeness"},
        "ripeness": {"ripeness", "disease_and_ripeness"},
        "security": {"security"},
        "intrusion": {"security"},
    }
    return etype in aliases.get(wanted, {wanted})


def _image_names(folder: Path, meta: dict) -> list:
    declared = meta.get("images") or []
    if isinstance(declared, list):
        names = [str(x) for x in declared if str(x)]
    else:
        names = []
    if not names:
        names = sorted(
            f.name for f in folder.iterdir()
            if f.suffix.lower() in (".jpg", ".jpeg", ".png", ".webp")
        )
    return names


def _event_to_record(meta_path: Path):
    try:
        meta = json.loads(meta_path.read_text(encoding="utf-8"))
    except Exception:
        return None
    folder = meta_path.parent
    when = _parse_event_time(meta, folder)
    if when is None:
        return None
    etype = _normalise_event_type(meta)
    label = meta.get("label")
    best = meta.get("disease_best") or meta.get("ripeness_best") or {}
    if not label:
        label = best.get("label", etype)
    if isinstance(label, str):
        label = label.replace("Security Camera:", "").replace("FarmMonitor:", "").strip()
    imgs = _image_names(folder, meta)
    try:
        rel_folder = folder.relative_to(Path(_B["STORAGE_PATH"]))
        image_urls = [f"/storage_img/{rel_folder.as_posix()}/{name}" for name in imgs]
    except Exception:
        image_urls = []
    rec = {
        "time": when.isoformat(timespec="seconds"),
        "date": when.strftime("%Y-%m-%d"),
        "clock": when.strftime("%H:%M:%S"),
        "folder": folder.name,
        "type": etype,
        "label": label or etype,
        "message": meta.get("message") or "",
        "confidence": meta.get("conf"),
        "images": len(imgs),
        "image_urls": image_urls[:3],
    }
    for key in ("usable_frames", "disease_ratio", "ripeness_ratio", "disease_best", "ripeness_best"):
        if key in meta:
            rec[key] = meta[key]
    return rec


def _all_storage_records(days_back: int = 14) -> list:
    root = Path(_B["STORAGE_PATH"])
    if not root.exists():
        return []
    cutoff = datetime.now() - timedelta(days=max(1, int(days_back)))
    records = []
    for meta_path in root.glob("*/*/*/*/meta.json"):
        rec = _event_to_record(meta_path)
        if rec is None:
            continue
        try:
            when = datetime.fromisoformat(rec["time"])
        except Exception:
            continue
        if when >= cutoff:
            records.append(rec)
    return sorted(records, key=lambda x: x["time"], reverse=True)


def _time_of_day(value: str):
    s = (value or "").strip()
    if not s:
        return None
    for fmt in ("%H:%M:%S", "%H:%M", "%I:%M%p", "%I%p"):
        try:
            return datetime.strptime(s.replace(" ", ""), fmt).time()
        except ValueError:
            pass
    return None


def get_storage_events(date: str = "", event_type: str = "", start_time: str = "",
                       end_time: str = "", hours: int = 0, limit: int = 20) -> str:
    """Extract real Storage_Data event metadata. Supports date, event type,
    start/end time, and recent-hour queries across days."""
    wanted = (event_type or "").strip().lower()
    limit = max(1, min(int(limit or 20), 50))

    try:
        hours_i = int(hours or 0)
    except (TypeError, ValueError):
        hours_i = 0

    if hours_i:
        cutoff = datetime.now() - timedelta(hours=max(1, hours_i))
        records = [
            r for r in _all_storage_records(days_back=max(2, int(hours_i / 24) + 2))
            if datetime.fromisoformat(r["time"]) >= cutoff
        ]
        date_label = f"last {hours_i} hour(s)"
    else:
        if not (date or "").strip():
            records = _all_storage_records(days_back=14)
            date_label = "recent activity"
        else:
            dt = _resolve_date(date or "today")
            if dt is None:
                return f"Invalid date '{date}'. Use 'today', 'yesterday' or 'YYYY-MM-DD'."
            root = (Path(_B["STORAGE_PATH"]) / dt.strftime("%Y") /
                    dt.strftime("%m") / dt.strftime("%d"))
            date_label = dt.strftime("%Y-%m-%d")
            records = []
            if root.exists():
                for meta_path in sorted(root.glob("*/meta.json")):
                    rec = _event_to_record(meta_path)
                    if rec:
                        records.append(rec)
                records.sort(key=lambda x: x["time"], reverse=True)

    if wanted:
        records = [r for r in records if _event_matches(r.get("type", ""), wanted)]

    start_t = _time_of_day(start_time)
    end_t = _time_of_day(end_time)
    if start_t or end_t:
        filtered = []
        for rec in records:
            t = datetime.fromisoformat(rec["time"]).time()
            if start_t and end_t and start_t <= end_t:
                ok = start_t <= t <= end_t
            elif start_t and end_t:
                ok = t >= start_t or t <= end_t
            elif start_t:
                ok = t >= start_t
            else:
                ok = t <= end_t
            if ok:
                filtered.append(rec)
        records = filtered

    summary = {}
    for rec in records:
        summary[rec["type"]] = summary.get(rec["type"], 0) + 1

    return _ok({
        "source": "Storage_Data",
        "period": date_label,
        "event_type_filter": wanted or "all",
        "start_time": start_time or None,
        "end_time": end_time or None,
        "total": len(records),
        "summary": summary,
        "events": records[:limit],
    })


# ════════════════════════════════════════════════════════════════════════════════
# TOOL 8-10 — scheduling (delegates to flora_scheduler)
# ════════════════════════════════════════════════════════════════════════════════

def schedule_task(tool_name: str = "", when: str = "",
                  tool_args: str = "{}", repeat: str = "once") -> str:
    """Schedule any read/action tool to run later. `when` accepts natural
    language: 'in 30 minutes', 'at 3:30PM', 'every day at 6AM'."""
    import flora_scheduler
    return flora_scheduler.add_task(tool_name, when, tool_args, repeat)


def get_schedule() -> str:
    """List all pending and recurring scheduled tasks."""
    import flora_scheduler
    return _ok(flora_scheduler.list_tasks())


def cancel_schedule(job_id: str = "") -> str:
    """Cancel a scheduled task by its job id."""
    import flora_scheduler
    return flora_scheduler.cancel_task(job_id)


# ════════════════════════════════════════════════════════════════════════════════
# TOOL 11-12 — auto irrigation
# ════════════════════════════════════════════════════════════════════════════════

def get_auto_irrigation() -> str:
    """Whether automatic burst irrigation is enabled, with its thresholds."""
    return _ok({
        "auto_irrigation": "enabled" if _B["get_auto"]() else "disabled",
        "starts_when_moisture_below_pct": _B["TRIGGER_PCT"],
        "stops_when_moisture_reaches_pct": _B["STOP_PCT"],
        "hardlock_pct": _B["LOCK_PCT"],
        "burst_cycle": f"{_B['BURST_ON_S']:.0f}s pump ON, then "
                       f"{_B['BURST_WAIT_S']:.0f}s soak, repeat until target",
    })


def set_auto_irrigation(enabled: bool = True) -> str:
    """Enable or disable automatic burst irrigation for all plants."""
    if isinstance(enabled, str):
        enabled = enabled.strip().lower() in ("true", "1", "yes", "on", "enable", "enabled")
    _B["set_auto"](bool(enabled))
    return (f"Automatic irrigation is now {'ENABLED' if enabled else 'DISABLED'}. "
            + ("Plants will be watered automatically when they get dry."
               if enabled else
               "Plants will only be watered manually. Any running auto-bursts "
               "stop within a second."))


# ════════════════════════════════════════════════════════════════════════════════
# TOOL 13 — set_farm_presence
# ════════════════════════════════════════════════════════════════════════════════

def set_farm_presence(at_farm: bool = True) -> str:
    """Set owner presence. Away mode arms the security guard."""
    if isinstance(at_farm, str):
        at_farm = at_farm.strip().lower() in ("true", "1", "yes", "on", "present", "here")
    _B["set_at_farm"](bool(at_farm))
    if at_farm:
        return "Marked as AT FARM. Security guard is OFF — you are present."
    return "Marked as AWAY. Security guard is ON — intrusions will be logged and alerted."


# ════════════════════════════════════════════════════════════════════════════════
# TOOL 14 — trigger_farm_scan
# ════════════════════════════════════════════════════════════════════════════════

def trigger_farm_scan() -> str:
    """Queue an immediate FarmMonitor plant-health / ripeness scan."""
    with _B["farm_scan_lock"]:
        state = _B["farm_scan_status"].get("state")
    if state == "scanning":
        return "A FarmMonitor scan is already running. Results will arrive shortly."
    _B["farm_scan_request"].set()
    return "FarmMonitor scan queued. It will analyse the plants for disease and ripeness."


# ════════════════════════════════════════════════════════════════════════════════
# TOOL 15 — get_analytics
# ════════════════════════════════════════════════════════════════════════════════

def get_analytics(hours: int = 24) -> str:
    """Numeric summary over the last N hours: moisture, detections, irrigation."""
    try:
        hours = max(1, min(int(hours), 168))
    except (TypeError, ValueError):
        hours = 24
    cutoff = time.time() - hours * 3600

    with _B["hist_lock"]:
        moisture = {}
        for p in _plants():
            pts = [e["v"] for e in _B["moisture_hist"].get(p, []) if e["t"] >= cutoff]
            if pts:
                moisture[p.upper()] = {
                    "avg": round(sum(pts) / len(pts), 1),
                    "min": round(min(pts), 1),
                    "max": round(max(pts), 1),
                }
        detections = [d for d in _B["detect_hist"] if d.get("t", 0) >= cutoff]
        irr_events = [e for e in _B["irr_hist"] if e.get("t", 0) >= cutoff]

    species = {}
    for d in detections:
        label = d.get("label", "unknown")
        if label not in ("No Sustained Event",):
            species[label] = species.get(label, 0) + 1

    irr_by_plant = {}
    for e in irr_events:
        pl = e.get("plant", "?").upper()
        irr_by_plant[pl] = irr_by_plant.get(pl, 0) + 1

    return _ok({
        "window_hours": hours,
        "moisture_summary": moisture or "no samples",
        "total_detections": len(detections),
        "detections_by_type": species or "none",
        "total_irrigation_events": len(irr_events),
        "irrigation_by_plant": irr_by_plant or "none",
    })


# ════════════════════════════════════════════════════════════════════════════════
# TOOL 16 — send_email
# ════════════════════════════════════════════════════════════════════════════════

def send_email(subject: str = "", message: str = "") -> str:
    """Email a message or short report to the farm's saved notification address.
    Works the same online or offline — it uses the server's own mail sender."""
    sender = _B.get("send_email")
    get_to = _B.get("get_notify_email")
    if sender is None or get_to is None:
        return "Email sending is not wired up on this server right now."
    to = (get_to() or "").strip()
    if not to:
        return ("There's no notification email saved yet 📭 — add one under "
                "Settings -> Email Notifications and I can send updates there.")
    subject = (subject or "").strip() or "🌿 FLORA Farm Update"
    message = (message or "").strip()
    if not message:
        return "Tell me what you'd like in the email and I'll send it right away."
    try:
        sender(subject, message)
        return f'📧 Sent — "{subject}" is on its way to {to}.'
    except Exception as exc:
        return f"I couldn't send that email: {exc}"


# ════════════════════════════════════════════════════════════════════════════════
# TOOL 17 — compile_report
# ════════════════════════════════════════════════════════════════════════════════

def compile_report(window_hours: int = 48) -> str:
    """Build a full designed PDF farm report and return a short-lived,
    authenticated download link. Works the same online or offline."""
    try:
        hours = int(window_hours)
    except (TypeError, ValueError):
        hours = 48
    hours = max(1, min(hours, 168))
    register = _B.get("register_report")
    if register is None:
        return "Report building is not wired up on this server right now."
    try:
        import flora_report
        info = flora_report.build_report(hours)
    except Exception as exc:
        return f"I couldn't build the report: {exc}"
    try:
        token = register(info["path"])
    except Exception as exc:
        return f"The report was built but couldn't be published: {exc}"
    return _ok({
        "ok": True,
        "download_url": f"/api/flora/report/{token}",
        "filename": info.get("filename", "FLORA_Farm_Report.pdf"),
        "pages": info.get("pages"),
        "window_hours": hours,
        "expires_in": "5 minutes",
    })


# ════════════════════════════════════════════════════════════════════════════════
# TOOL 18 — email_report
# ════════════════════════════════════════════════════════════════════════════════

def email_report(window_hours: int = 48) -> str:
    """Build a PDF farm report and email it as an attachment to the saved
    notification address — no link, the PDF travels with the email."""
    try:
        hours = int(window_hours)
    except (TypeError, ValueError):
        hours = 48
    hours = max(1, min(hours, 168))
    emailer = _B.get("email_report")
    if emailer is None:
        return "Emailing reports is not wired up on this server right now."
    try:
        import flora_report
        info = flora_report.build_report(hours)
    except Exception as exc:
        return f"I couldn't build the report: {exc}"
    subject = f"🌿 FLORA Farm Report — last {hours} hours"
    body = (f"Hello!\n\nYour FLORA farm report for the last {hours} hours is "
            f"attached as a PDF — it covers farm status, moisture, security, "
            f"plant health & harvest, and irrigation.\n\nWarm regards,\nFLORA 🌿")
    try:
        ok, detail = emailer(subject, body, info["path"])
    except Exception as exc:
        ok, detail = False, str(exc)
    try:
        Path(info["path"]).unlink(missing_ok=True)
    except Exception:
        pass
    if ok:
        return (f"📧 Your {hours}-hour farm report (PDF attached) has been "
                f"emailed to {detail}.")
    return (f"I built the report but couldn't email it — {detail}. Add a "
            f"notification email under Settings -> Email Notifications.")


# ════════════════════════════════════════════════════════════════════════════════
# Tool dispatcher
# ════════════════════════════════════════════════════════════════════════════════

def set_camera(camera: str = "all", on: bool = True) -> str:
    """Turn a camera's monitoring ON or OFF (security / farmmonitor / all)."""
    cam = (camera or "all").strip().lower()
    fn = _B.get("set_camera")
    if not fn:
        return "Camera control is not available right now."
    if isinstance(on, str):
        on = on.strip().lower() not in ("off", "false", "0", "no", "disable")
    fn(cam, bool(on))
    names = {"security": "Security camera", "sec": "Security camera",
             "rpi": "Security camera", "farmmonitor": "FarmMonitor camera",
             "farm": "FarmMonitor camera", "monitor": "FarmMonitor camera",
             "all": "Both cameras"}
    return f"📷 {names.get(cam, camera)} monitoring turned {'ON' if on else 'OFF'}."


def email_detections(hours: int = 24, event_type: str = "") -> str:
    """Email the most recent detection snapshots (security + farm) attached
    directly to the saved address — real images, not a PDF link."""
    try:
        hours = max(1, min(int(hours or 24), 168))
    except Exception:
        hours = 24
    fn = _B.get("email_images")
    if not fn:
        return "Direct image email is not available right now."
    cutoff = datetime.now() - timedelta(hours=hours)
    paths, lines = [], []
    for r in _all_storage_records(days_back=max(2, int(hours / 24) + 2)):
        try:
            when = datetime.fromisoformat(r["time"])
        except Exception:
            continue
        if when < cutoff:
            continue
        if event_type and not _event_matches(r.get("type", ""), event_type):
            continue
        for u in (r.get("image_urls") or []):
            p = Path(_B["STORAGE_PATH"]) / u.replace("/storage_img/", "", 1)
            if p.exists():
                paths.append(p)
        if r.get("image_urls"):
            lines.append(f"• {r.get('date','')} {r.get('clock','')} — "
                         f"{r.get('label') or r.get('type')}")
        if len(paths) >= 8:
            break
    if not paths:
        return f"I found no detection snapshots in the last {hours}h to email."
    body = (f"FLORA farm detections — last {hours}h\n\n"
            + "\n".join(lines[:8]) + "\n\nSnapshots attached. 🌿")
    ok, detail = fn(f"🌿 FLORA — {len(paths)} detection image(s), last {hours}h",
                    body, paths)
    return (f"📧 Sent {len(paths)} detection image(s) from the last {hours}h to {detail}."
            if ok else f"I couldn't send the images: {detail}.")


def set_notification_email(email: str = "") -> str:
    """Save the farm notification email address (FLORA settings control)."""
    fn = _B.get("set_notify_email")
    if not fn:
        return "Settings control is not available right now."
    ok, detail = fn(email)
    return (f"✅ Notification email set to {detail}." if ok
            else f"I couldn't set that email: {detail}.")


def test_buzzer() -> str:
    """Fire a short test beep on both intruder buzzers."""
    fn = _B.get("test_buzzer")
    if not fn:
        return "Buzzer control is not available right now."
    ok, detail = fn()
    return ("🔔 Testing the intruder buzzers now — you should hear three beeps."
            if ok else f"I couldn't test the buzzers: {detail}.")


def set_siren(enabled: bool = True) -> str:
    """Mute or unmute the intruder siren that sounds on a security-camera threat."""
    fn = _B.get("set_siren")
    if not fn:
        return "Siren control is not available right now."
    on = fn(enabled)
    return (f"🔔 Intruder siren is now {'armed' if on else 'muted'}.")


_TOOL_MAP = {
    "get_farm_status":     lambda a: get_farm_status(),
    "get_moisture":        lambda a: get_moisture(a.get("plant", "")),
    "irrigate_plant":      lambda a: irrigate_plant(a.get("plant", "")),
    "stop_pump":           lambda a: stop_pump(a.get("plant", "")),
    "get_camera_status":   lambda a: get_camera_status(a.get("camera", "all")),
    "set_camera":          lambda a: set_camera(a.get("camera", "all"), a.get("on", True)),
    "analyze_farm":        lambda a: analyze_farm(a.get("period", "1h")),
    "get_storage_events":  lambda a: get_storage_events(
        a.get("date", ""),
        a.get("event_type", ""),
        a.get("start_time", ""),
        a.get("end_time", ""),
        a.get("hours", 0),
        a.get("limit", 20),
    ),
    "schedule_task":       lambda a: schedule_task(a.get("tool_name", ""),
                                                   a.get("when", ""),
                                                   a.get("tool_args", "{}"),
                                                   a.get("repeat", "once")),
    "get_schedule":        lambda a: get_schedule(),
    "cancel_schedule":     lambda a: cancel_schedule(a.get("job_id", "")),
    "get_auto_irrigation": lambda a: get_auto_irrigation(),
    "set_auto_irrigation": lambda a: set_auto_irrigation(a.get("enabled", True)),
    "set_farm_presence":   lambda a: set_farm_presence(a.get("at_farm", True)),
    "trigger_farm_scan":   lambda a: trigger_farm_scan(),
    "get_analytics":       lambda a: get_analytics(a.get("hours", 24)),
    "send_email":          lambda a: send_email(a.get("subject", ""),
                                                a.get("message", "")),
    "compile_report":      lambda a: compile_report(a.get("window_hours", 48)),
    "email_report":        lambda a: email_report(a.get("window_hours", 48)),
    "email_detections":    lambda a: email_detections(a.get("hours", 24), a.get("event_type", "")),
    "set_notification_email": lambda a: set_notification_email(a.get("email", "")),
    "test_buzzer":         lambda a: test_buzzer(),
    "set_siren":           lambda a: set_siren(a.get("enabled", True)),
}

# Tool names a scheduled task is allowed to invoke (no recursion into scheduler).
SCHEDULABLE_TOOLS = sorted(set(_TOOL_MAP) - {"schedule_task", "cancel_schedule"})


def execute_tool(name: str, args: dict) -> str:
    """Run a registered tool by name. Always returns a string, never raises."""
    if not is_ready():
        return "FLORA tools are not initialised yet — try again in a moment."
    fn = _TOOL_MAP.get(name)
    if fn is None:
        return f"Unknown tool '{name}'. Available tools: {', '.join(sorted(_TOOL_MAP))}."
    if not isinstance(args, dict):
        args = {}
    try:
        return str(fn(args))
    except Exception as exc:  # defensive — a tool fault must not crash the agent
        return f"Tool '{name}' failed: {exc}"


# ════════════════════════════════════════════════════════════════════════════════
# OpenAI function-calling specifications
# ════════════════════════════════════════════════════════════════════════════════

def _fn(name, description, properties=None, required=None):
    return {
        "type": "function",
        "function": {
            "name": name,
            "description": description,
            "parameters": {
                "type": "object",
                "properties": properties or {},
                "required": required or [],
            },
        },
    }


_PLANT_PROP = {"type": "string", "description": "Plant id A-H"}

TOOL_SPECS = [
    _fn("get_farm_status", "Full farm snapshot: every active plant's moisture, sensors, "
        "pumps, plus auto-irrigation, guard and alerts."),
    _fn("get_moisture", "Moisture for one plant or all eight.",
        {"plant": {"type": "string", "description": "Plant A-H, or empty for all"}}),
    _fn("irrigate_plant", "Start the water pump for a plant. Refused if the sensor "
        "is offline or moisture is at/above the 70% hardlock.",
        {"plant": _PLANT_PROP}, ["plant"]),
    _fn("stop_pump", "Stop the water pump for a plant immediately.",
        {"plant": _PLANT_PROP}, ["plant"]),
    _fn("get_camera_status", "Status of the Security and FarmMonitor cameras.",
        {"camera": {"type": "string", "enum": ["all", "security", "farmmonitor"]}}),
    _fn("analyze_farm", "Narrative analysis of moisture, detections and irrigation "
        "over a window.",
        {"period": {"type": "string", "description": "e.g. 30m, 1h, 6h, 24h"}}),
    _fn("get_storage_events", "Extract real event history from Storage_Data. "
        "Use this before answering any question about what happened, stored "
        "events, security history, disease history, harvest/ripeness history, "
        "or a time window.",
        {"date": {"type": "string", "description": "today, yesterday or YYYY-MM-DD. Leave empty when using hours."},
         "event_type": {"type": "string",
                        "description": "optional filter: security, disease, ripeness, harvest, farmmonitor"},
         "start_time": {"type": "string", "description": "optional HH:MM start time, e.g. 21:00"},
         "end_time": {"type": "string", "description": "optional HH:MM end time, e.g. 22:00"},
         "hours": {"type": "integer", "description": "optional: look back this many hours across days"},
         "limit": {"type": "integer", "description": "maximum event records to return, default 20"}}),
    _fn("schedule_task", "Schedule a tool to run later. `when` is natural language.",
        {"tool_name": {"type": "string", "description": "tool to run, e.g. get_moisture"},
         "when": {"type": "string", "description": "'in 30 minutes', 'at 3:30PM', "
                  "'every day at 6AM'"},
         "tool_args": {"type": "string", "description": "JSON string of tool args"},
         "repeat": {"type": "string", "enum": ["once", "daily"]}},
        ["tool_name", "when"]),
    _fn("get_schedule", "List all pending and recurring scheduled tasks."),
    _fn("cancel_schedule", "Cancel a scheduled task by job id.",
        {"job_id": {"type": "string"}}, ["job_id"]),
    _fn("get_auto_irrigation", "Check whether automatic burst irrigation is enabled."),
    _fn("set_auto_irrigation", "Enable or disable automatic irrigation.",
        {"enabled": {"type": "boolean"}}, ["enabled"]),
    _fn("set_farm_presence", "Set owner presence. Away mode arms the security guard.",
        {"at_farm": {"type": "boolean", "description": "true = at farm, false = away"}},
        ["at_farm"]),
    _fn("trigger_farm_scan", "Queue an immediate FarmMonitor disease/ripeness scan."),
    _fn("get_analytics", "Numeric summary over the last N hours.",
        {"hours": {"type": "integer", "description": "1-168, default 24"}}),
    _fn("send_email", "Email a plain text message to the farm's saved "
        "notification address. For emailing a farm REPORT use email_report "
        "instead (never put report links in send_email).",
        {"subject": {"type": "string", "description": "email subject line"},
         "message": {"type": "string", "description": "the email body text"}},
        ["message"]),
    _fn("compile_report", "Build a full designed PDF farm report (status, "
        "moisture, security/intruders, plant health & harvest, irrigation) for "
        "the last N hours, default 48, and show a download button in the chat. "
        "Use when the user wants to view or download a report. To EMAIL a report "
        "use email_report instead. After it runs, warmly say the PDF is ready to "
        "download below — never paste a raw link.",
        {"window_hours": {"type": "integer",
                           "description": "report window in hours, default 48"}}),
    _fn("email_report", "Build a PDF farm report for the last N hours (default "
        "48) and EMAIL it as an attachment to the saved address. Use this "
        "whenever the user wants a report emailed or sent to them — it is the "
        "only correct way to email a report (the PDF is attached, no link).",
        {"window_hours": {"type": "integer",
                           "description": "report window in hours, default 48"}}),
    _fn("set_camera", "Turn a camera's monitoring ON or OFF — the security camera, "
        "the FarmMonitor camera, or both. Schedulable (e.g. 'turn the security "
        "camera off at 10pm and back on at 6am').",
        {"camera": {"type": "string", "enum": ["security", "farmmonitor", "all"]},
         "on": {"type": "boolean", "description": "true = on, false = off"}},
        ["camera", "on"]),
    _fn("email_detections", "Email the most recent detection snapshots (security "
        "and FarmMonitor) attached directly as image files to the saved address. "
        "Use when the user wants the actual detection photos sent, not a PDF.",
        {"hours": {"type": "integer", "description": "look back this many hours, default 24"},
         "event_type": {"type": "string", "description": "optional filter: security, "
                        "farmmonitor (disease+ripeness), disease, ripeness"}}),
    _fn("set_notification_email", "Save or change the farm's notification email address.",
        {"email": {"type": "string", "description": "the email address to save"}},
        ["email"]),
    _fn("test_buzzer", "Fire a short test beep on both intruder buzzers to check they work."),
    _fn("set_siren", "Arm or mute the intruder siren that sounds when the security "
        "camera detects a threat while the guard is active.",
        {"enabled": {"type": "boolean", "description": "true = armed, false = muted"}},
        ["enabled"]),
]
