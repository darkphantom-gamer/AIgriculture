"""
FLORA Intelligence — task scheduler.

Wraps APScheduler so FLORA can run any registered tool at a future time, with
natural-language time parsing ('in 30 minutes', 'at 3:30PM', 'every day at 6AM').

One-shot jobs delete themselves from disk after running. Recurring (daily) jobs
persist until cancelled. Job results are pushed to FLORA's WebSocket clients.
"""
import json
import re
import time
import uuid
from datetime import datetime, timedelta

import flora_config as config

try:
    from apscheduler.schedulers.background import BackgroundScheduler
    from apscheduler.triggers.date import DateTrigger
    from apscheduler.triggers.cron import CronTrigger
    _APS_AVAILABLE = True
except ImportError:  # pragma: no cover
    _APS_AVAILABLE = False

_scheduler = None          # the BackgroundScheduler instance
_broadcast_fn = None       # async fn to push results to WebSocket clients
_event_loop = None         # the uvicorn asyncio loop


# ── Runtime wiring ──────────────────────────────────────────────────────────────

def set_runtime(broadcast_fn, event_loop) -> None:
    """Give the scheduler the broadcast coroutine + loop for pushing results."""
    global _broadcast_fn, _event_loop
    _broadcast_fn = broadcast_fn
    _event_loop = event_loop


def start():
    """Create and start the scheduler, then reload persisted jobs. Returns it."""
    global _scheduler
    if not _APS_AVAILABLE:
        print("[FLORA] APScheduler not installed — scheduling disabled")
        return None
    if _scheduler is None:
        _scheduler = BackgroundScheduler()
        _scheduler.start()
        _reload_jobs()
    return _scheduler


# ── Persistence (.flora_schedule.json) ──────────────────────────────────────────

def _read_store() -> dict:
    try:
        if config.FLORA_SCHEDULE_FILE.exists():
            return json.loads(config.FLORA_SCHEDULE_FILE.read_text(encoding="utf-8"))
    except Exception:
        pass
    return {}


def _write_store(store: dict) -> None:
    try:
        config.FLORA_SCHEDULE_FILE.write_text(
            json.dumps(store, indent=2), encoding="utf-8")
    except Exception as exc:  # pragma: no cover
        print(f"[FLORA] schedule store write failed: {exc}")


def _store_remove(job_id: str) -> None:
    store = _read_store()
    if job_id in store:
        del store[job_id]
        _write_store(store)


# ── Natural-language time parser ────────────────────────────────────────────────

# A scheduled one-shot task may be planned at most this far ahead.
_MAX_HORIZON = timedelta(hours=24)
_TOO_FAR = ("I can only plan up to 24 hours ahead \U0001f319 — "
            "please pick a sooner time.")


def _parse_when(when: str):
    """Return (trigger, human_str, repeat). Raises ValueError on bad input."""
    s = (when or "").lower().strip()
    now = datetime.now()

    # recurring — "every day at 6am" / "daily at 18:30"
    m = re.search(r'(every day|daily)\s+at\s+(.+)', s)
    if m:
        t = _parse_clock(m.group(2))
        if t is None:
            raise ValueError(f"Can't read the time in '{when}'.")
        return (CronTrigger(hour=t[0], minute=t[1]),
                f"every day at {t[0]:02d}:{t[1]:02d}", "daily")

    # relative — "in 30 minutes" / "after 2 hours"
    m = re.match(r'(in|after)\s+(\d+)\s*(second|minute|hour|day)s?', s)
    if m:
        n, unit = int(m.group(2)), m.group(3)
        delta = {
            "second": timedelta(seconds=n),
            "minute": timedelta(minutes=n),
            "hour":   timedelta(hours=n),
            "day":    timedelta(days=n),
        }[unit]
        run_at = now + delta
        if run_at - now > _MAX_HORIZON:
            raise ValueError(_TOO_FAR)
        return (DateTrigger(run_date=run_at),
                run_at.strftime("%Y-%m-%d %H:%M:%S"), "once")

    # absolute clock — "at 3:30pm" / "at 14:30" / "9am"
    t = _parse_clock(re.sub(r'^(at|tomorrow at)\s*', '', s))
    if t is not None:
        run_at = now.replace(hour=t[0], minute=t[1], second=0, microsecond=0)
        if s.startswith("tomorrow") or run_at <= now:
            run_at += timedelta(days=1)
        if run_at - now > _MAX_HORIZON:
            raise ValueError(_TOO_FAR)
        return (DateTrigger(run_date=run_at),
                run_at.strftime("%Y-%m-%d %H:%M:%S"), "once")

    raise ValueError(
        f"Can't understand the time '{when}'. Try 'in 20 minutes', "
        "'at 3:30PM', '14:00' or 'every day at 6AM'.")


def _parse_clock(text: str):
    """Parse a clock string into (hour, minute), or None."""
    clean = (text or "").replace(" ", "").upper()
    for fmt in ("%I:%M%p", "%I%p", "%H:%M", "%H"):
        try:
            t = datetime.strptime(clean, fmt)
            return (t.hour, t.minute)
        except ValueError:
            continue
    return None


# ── Job execution ───────────────────────────────────────────────────────────────

def _run_job(job_id: str, tool_name: str, tool_args_json: str, repeat: str) -> None:
    """Executed by APScheduler in a worker thread when a job fires."""
    import flora_tools
    result = ""
    try:
        try:
            args = json.loads(tool_args_json) if tool_args_json else {}
        except Exception:
            args = {}
        if not isinstance(args, dict):
            args = {}
        result = flora_tools.execute_tool(tool_name, args)
    except Exception as exc:
        result = f"Scheduled task error: {exc}"
    finally:
        if repeat != "daily":
            _store_remove(job_id)
        friendly = f"✅ Scheduled task '{tool_name}' finished.\n{str(result)}".strip()
        # Persist so the outcome is visible the next time FLORA chat opens,
        # even if no client was connected when the job fired.
        try:
            import flora_agent
            flora_agent._save_history(f"[scheduled task: {tool_name}]", friendly)
        except Exception:
            pass
        if _broadcast_fn and _event_loop and _event_loop.is_running():
            import asyncio
            try:
                asyncio.run_coroutine_threadsafe(
                    _broadcast_fn({
                        "type": "scheduled_result",
                        "job_id": job_id,
                        "tool": tool_name,
                        "result": str(result),
                        "summary": friendly,
                    }),
                    _event_loop,
                )
            except Exception as exc:  # pragma: no cover
                print(f"[FLORA] scheduled_result broadcast failed: {exc}")


# ── Public API (called by flora_tools) ──────────────────────────────────────────

def add_task(tool_name: str, when: str, tool_args: str = "{}",
             repeat: str = "once") -> str:
    """Register a scheduled task. Returns a human-readable confirmation."""
    import flora_tools
    if _scheduler is None:
        return "Scheduling is unavailable (APScheduler not installed on the server)."

    tool_name = (tool_name or "").strip()
    if tool_name not in flora_tools.SCHEDULABLE_TOOLS:
        return (f"Cannot schedule '{tool_name}'. Schedulable tools: "
                f"{', '.join(flora_tools.SCHEDULABLE_TOOLS)}.")

    # validate args are JSON
    if isinstance(tool_args, dict):
        tool_args = json.dumps(tool_args)
    try:
        json.loads(tool_args or "{}")
    except Exception:
        return f"tool_args must be a valid JSON string, got: {tool_args!r}"

    try:
        trigger, human, resolved_repeat = _parse_when(when)
    except ValueError as exc:
        return str(exc)

    job_id = f"flora-{uuid.uuid4().hex[:8]}"
    _scheduler.add_job(
        _run_job, trigger=trigger, id=job_id,
        args=[job_id, tool_name, tool_args or "{}", resolved_repeat],
        replace_existing=True, misfire_grace_time=120,
    )

    _job = _scheduler.get_job(job_id)
    run_at_iso = (_job.next_run_time.strftime("%Y-%m-%d %H:%M:%S")
                  if _job and _job.next_run_time else "")

    store = _read_store()
    store[job_id] = {
        "tool_name": tool_name,
        "tool_args": tool_args or "{}",
        "when": when,
        "repeat": resolved_repeat,
        "run_at": human,
        "run_at_iso": run_at_iso,
        "created": datetime.now().isoformat(timespec="seconds"),
    }
    _write_store(store)
    return (f"Scheduled '{tool_name}' to run {human}"
            + (" (repeats daily)" if resolved_repeat == "daily" else "")
            + f". Job id: {job_id}")


def list_tasks() -> list:
    """Return all scheduled tasks (pending one-shots + recurring)."""
    store = _read_store()
    tasks = []
    for job_id, info in store.items():
        live = _scheduler.get_job(job_id) if _scheduler else None
        next_run = None
        if live and live.next_run_time:
            next_run = live.next_run_time.strftime("%Y-%m-%d %H:%M:%S")
        run_at_iso = next_run or info.get("run_at_iso") or ""
        tasks.append({
            "job_id": job_id,
            "tool_name": info.get("tool_name"),
            "tool_args": info.get("tool_args", "{}"),
            "repeat": info.get("repeat", "once"),
            "run_at": info.get("run_at") or run_at_iso,
            "run_at_iso": run_at_iso,
            "status": "scheduled" if live else "pending",
        })
    tasks.sort(key=lambda t: t.get("run_at_iso") or "")
    return tasks


def cancel_task(job_id: str) -> str:
    """Cancel a scheduled task by id."""
    job_id = (job_id or "").strip()
    if not job_id:
        return "Provide the job id to cancel (see get_schedule)."
    found = False
    if _scheduler and _scheduler.get_job(job_id):
        _scheduler.remove_job(job_id)
        found = True
    store = _read_store()
    if job_id in store:
        del store[job_id]
        _write_store(store)
        found = True
    return f"Cancelled scheduled task {job_id}." if found else \
           f"No scheduled task with id '{job_id}'."


# ── Startup reload ──────────────────────────────────────────────────────────────

def _reload_jobs() -> None:
    """Re-register surviving jobs from disk; drop one-shots that already elapsed."""
    store = _read_store()
    if not store:
        return
    now = datetime.now()
    kept = {}
    for job_id, info in store.items():
        repeat = info.get("repeat", "once")
        try:
            if repeat == "daily":
                hh, mm = [int(x) for x in info["run_at"].split("at")[-1].strip().split(":")]
                trigger = CronTrigger(hour=hh, minute=mm)
            else:
                run_at = datetime.strptime(info["run_at"], "%Y-%m-%d %H:%M:%S")
                if run_at <= now:
                    continue  # already elapsed — drop it
                trigger = DateTrigger(run_date=run_at)
            _scheduler.add_job(
                _run_job, trigger=trigger, id=job_id,
                args=[job_id, info["tool_name"], info.get("tool_args", "{}"), repeat],
                replace_existing=True, misfire_grace_time=120,
            )
            kept[job_id] = info
        except Exception as exc:
            print(f"[FLORA] could not reload job {job_id}: {exc}")
    if kept != store:
        _write_store(kept)
    if kept:
        print(f"[FLORA] reloaded {len(kept)} scheduled task(s)")
