"""FastAPI application factory.

create_app(state) builds the dashboard API and wires it to the live AppState
(irrigation engine, siren, cameras). FLORA and FarmMonitor routes are present
as safe stubs and become live when those subsystems are attached to the state.
"""

from __future__ import annotations

import asyncio
import time
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Callable

from fastapi import Depends, FastAPI, Form, Request, WebSocket, WebSocketDisconnect
from fastapi.responses import (FileResponse, HTMLResponse, JSONResponse,
                               RedirectResponse, Response, StreamingResponse)

from .. import config
from ..config import PLANTS
from . import auth

STATIC_DIR = Path(__file__).parent / "static"
_IMG_TYPES = {".png": "image/png", ".jpg": "image/jpeg", ".jpeg": "image/jpeg", ".svg": "image/svg+xml"}


def _mjpeg(get_jpeg: Callable[[], bytes | None]):
    """Yield a multipart MJPEG stream from a frame-producing callable."""
    boundary = b"--frame\r\n"
    blank_until = 0.0
    while True:
        jpeg = get_jpeg()
        if jpeg:
            yield boundary + b"Content-Type: image/jpeg\r\n\r\n" + jpeg + b"\r\n"
        else:
            time.sleep(0.1)
        time.sleep(0.05)


def create_app(state) -> FastAPI:
    @asynccontextmanager
    async def lifespan(app_: FastAPI):
        state.loop = asyncio.get_running_loop()
        auth.ensure_admin()
        state.irrigation.start()
        if state.security:
            state.security.start()
        pusher = asyncio.create_task(_push_loop())
        try:
            yield
        finally:
            pusher.cancel()
            state.irrigation.stop()
            if state.security:
                state.security.stop()

    app = FastAPI(title="AIgriculture", lifespan=lifespan)

    async def _push_loop():
        while True:
            await asyncio.sleep(2.0)
            try:
                await state.broadcast(state.state_snapshot())
            except Exception:
                pass

    # ── middleware + auth redirect ────────────────────────────────────────────
    @app.middleware("http")
    async def _headers(request: Request, call_next):
        resp = await call_next(request)
        return auth.apply_security_headers(resp, request)

    @app.exception_handler(auth.AuthRedirect)
    async def _auth_redirect(request, exc):
        return auth.no_store(RedirectResponse(url="/login", status_code=303))

    # ── pages ────────────────────────────────────────────────────────────────
    def _page(name: str) -> str:
        f = STATIC_DIR / name
        return f.read_text(encoding="utf-8") if f.exists() else f"<h1>{name} missing</h1>"

    @app.get("/login", response_class=HTMLResponse)
    async def login_page(request: Request):
        if auth.session_user(request.cookies.get(auth.COOKIE_NAME)):
            return auth.no_store(RedirectResponse(url="/", status_code=303))
        return auth.no_store(HTMLResponse(_page("login.html")))

    @app.get("/", response_class=HTMLResponse)
    async def dashboard(_user: str = Depends(auth.require_auth)):
        return auth.no_store(HTMLResponse(_page("essential.html")))

    # ── auth ──────────────────────────────────────────────────────────────────
    @app.post("/auth/login")
    async def auth_login(request: Request, username: str = Form(...), password: str = Form(...)):
        ip = request.client.host if request.client else "unknown"
        if not auth.check_rate_limit(ip):
            return auth.no_store(JSONResponse(
                {"ok": False, "error": "Too many attempts. Try again in 15 minutes."}, status_code=429))
        user = await asyncio.get_running_loop().run_in_executor(
            None, auth.verify_credentials, username.strip(), password)
        if not user:
            return auth.no_store(JSONResponse({"ok": False, "error": "Invalid credentials."}, status_code=401))
        auth.reset_rate_limit(ip)
        token, _ = await asyncio.get_running_loop().run_in_executor(None, auth.create_token, user["username"])
        resp = JSONResponse({"ok": True, "username": user["username"]})
        resp.set_cookie(auth.COOKIE_NAME, token, httponly=True, samesite="strict",
                        max_age=auth.JWT_EXPIRE_HRS * 3600, path="/", secure=auth.is_https(request))
        return auth.no_store(resp)

    @app.post("/auth/logout")
    async def auth_logout(request: Request):
        token = request.cookies.get(auth.COOKIE_NAME)
        payload = auth._decode(token) if token else None
        if payload:
            auth.db.revoke_session(payload.get("jti", ""))
        resp = RedirectResponse(url="/login", status_code=303)
        resp.delete_cookie(auth.COOKIE_NAME, path="/")
        return auth.no_store(resp)

    # ── identity / health ─────────────────────────────────────────────────────
    @app.get("/healthz")
    @app.get("/api/health")
    def health(_user: str = Depends(auth.require_auth)):
        return JSONResponse(state.health(), headers={"Cache-Control": "no-store"})

    @app.get("/api/me")
    def api_me(_user: str = Depends(auth.require_auth)):
        profile = auth.get_user_profile(_user)
        return JSONResponse({**profile, "permissions": auth.user_permissions(profile["role"])},
                            headers={"Cache-Control": "no-store"})

    # ── live state + websocket ─────────────────────────────────────────────────
    @app.get("/api/state")
    def api_state(_user: str = Depends(auth.require_auth)):
        return JSONResponse(state.state_snapshot())

    @app.get("/alerts")
    def alerts(_user: str = Depends(auth.require_auth)):
        return JSONResponse({"alerts": [a["name"] for a in state.active_alerts()],
                             "at_farm": state.at_farm, "detail": state.active_alerts()})

    @app.websocket("/ws")
    async def ws(websocket: WebSocket):
        if not auth.session_user(websocket.cookies.get(auth.COOKIE_NAME)):
            await websocket.close(code=1008)
            return
        await websocket.accept()
        with state.ws_lock:
            state.ws_clients.append(websocket)
        try:
            await websocket.send_text(__import__("json").dumps(state.state_snapshot()))
            while True:
                await websocket.receive_text()
        except WebSocketDisconnect:
            pass
        finally:
            with state.ws_lock:
                if websocket in state.ws_clients:
                    state.ws_clients.remove(websocket)

    # ── sensors: scan + hot-add ─────────────────────────────────────────────────
    @app.get("/api/sensors/scan")
    def sensors_scan(_user: str = Depends(auth.require_auth)):
        rows = state.irrigation.sensors.scan_bus()
        unassigned = [r for r in rows if r["plausible"] and not r["assigned_to"]]
        return JSONResponse({"channels": rows, "unassigned": unassigned,
                             "i2c_available": state.irrigation.sensors.available})

    @app.post("/api/sensors/add")
    async def sensors_add(data: dict, _user: str = Depends(auth.require_admin)):
        """Auto-add up to `count` sensors. Scans the I2C bus, finds plausible
        channels not yet assigned, and binds them to fresh plant letters. Any
        relay pin assignments are optional — pass `relay_pins: [...]` to also
        register pumps for those new plants."""
        import json
        count = int(data.get("count", 1))
        relay_pins = list(data.get("relay_pins") or [])
        if count <= 0:
            return JSONResponse({"ok": False, "error": "count must be > 0"}, status_code=400)
        free = state.irrigation.sensors.unassigned_channels()
        if len(free) < count:
            return JSONResponse({
                "ok": False, "error": "not_enough_sensors_plugged_in",
                "found_unassigned": len(free), "requested": count,
                "message": (f"Only {len(free)} unassigned sensor(s) detected on the I2C bus. "
                            f"Plug the rest in and rescan."),
            }, status_code=409)
        # Pick the next free plant letters (a..p).
        used = set(state.plant_names.keys())
        new_letters = [chr(ord('a') + i) for i in range(16) if chr(ord('a') + i) not in used][:count]
        assigned = []
        for i, letter in enumerate(new_letters):
            ch = free[i]
            state.irrigation.sensors.add_channel(letter, ch["addr"], ch["channel"])
            relay_pin = None
            if i < len(relay_pins):
                try:
                    relay_pin = int(relay_pins[i])
                    state.irrigation.relay.add_pin(letter, relay_pin)
                except (TypeError, ValueError):
                    relay_pin = None
            state.irrigation.add_plant(letter)
            state.add_plant(letter)
            if letter not in state.active_plants:
                state.active_plants.append(letter)
                state.active_plants.sort()
            assigned.append({"plant": letter, "addr": ch["addr"], "channel": ch["channel"],
                             "relay_pin": relay_pin, "raw": ch["raw"]})
        # Persist so additions survive a restart.
        try:
            persist = config.RUNTIME_DIR / "plants.json"
            existing: dict = {}
            if persist.exists():
                try:
                    existing = json.loads(persist.read_text(encoding="utf-8")) or {}
                except Exception:
                    existing = {}
            for a in assigned:
                existing[a["plant"]] = {
                    "moisture": {"addr": a["addr"], "channel": a["channel"]},
                    "relay_pin": a["relay_pin"],
                }
            config.RUNTIME_DIR.mkdir(parents=True, exist_ok=True)
            persist.write_text(json.dumps(existing, indent=2), encoding="utf-8")
        except Exception as e:
            print(f"[WARN] could not persist plants.json: {e}")
        return JSONResponse({"ok": True, "added": assigned})

    # ── irrigation + plant control ─────────────────────────────────────────────
    @app.get("/api/plants")
    def list_plants(_user: str = Depends(auth.require_auth)):
        all_plants = list(state.plant_names.keys())
        return JSONResponse({"active": state.active_plants, "all": all_plants,
                             "names": state.plant_names, "pumps": all_plants})

    @app.post("/api/plants/{plant}/{action}")
    def set_plant_active(plant: str, action: str, _user: str = Depends(auth.require_admin)):
        plant = plant.lower()
        if plant not in state.plant_names or action not in ("enable", "disable"):
            return JSONResponse({"ok": False, "error": "invalid"}, status_code=400)
        if action == "enable" and plant not in state.active_plants:
            state.active_plants.append(plant)
            state.active_plants.sort()
        elif action == "disable" and plant in state.active_plants:
            state.active_plants.remove(plant)
            state.irrigation.command_burst(plant, False)
        return JSONResponse({"ok": True, "active": state.active_plants})

    @app.post("/api/pump/{plant}/{action}")
    def pump_ctrl(plant: str, action: str, _user: str = Depends(auth.require_admin)):
        plant = plant.lower()
        if plant not in state.plant_names or action not in ("on", "off"):
            return JSONResponse({"ok": False, "error": "invalid"}, status_code=400)
        if action == "on":
            snap = state.irrigation.snapshot()["plants"][plant]
            mv, online = snap["moisture"], snap["online"]
            if online and mv is not None and mv >= config.LOCK_PCT:
                return JSONResponse({"ok": False, "error": "locked", "moisture": mv, "lock_at": config.LOCK_PCT})
            state.irrigation.command_burst(plant, True)
            warn = None if online else "sensor_offline"
            payload = {"ok": True, "plant": plant, "on": True}
            if warn:
                payload.update({"warning": "sensor_offline_manual_override", "sensor_error": warn})
            return JSONResponse(payload)
        state.irrigation.command_burst(plant, False)
        return JSONResponse({"ok": True, "plant": plant, "on": False})

    @app.post("/api/auto_irrigation")
    async def set_auto(data: dict, _user: str = Depends(auth.require_admin)):
        state.irrigation.set_auto(bool(data.get("enabled", True)))
        return JSONResponse({"ok": True, "enabled": state.irrigation.auto_enabled})

    # ── presence + siren + camera ──────────────────────────────────────────────
    @app.post("/set_presence")
    async def set_presence(data: dict, _user: str = Depends(auth.require_admin)):
        state.at_farm = bool(data.get("at_farm", False))
        if state.at_farm:
            state.siren.arm(False)
        return JSONResponse({"ok": True, "at_farm": state.at_farm})

    @app.post("/api/buzzer")
    async def buzzer_mute(data: dict, _user: str = Depends(auth.require_admin)):
        state.siren.enabled = bool(data.get("enabled", True))
        if not state.siren.enabled:
            state.siren.arm(False)
        return JSONResponse({"ok": True, "enabled": state.siren.enabled, "available": state.siren.available})

    @app.post("/api/buzzer/test")
    async def buzzer_test(_user: str = Depends(auth.require_admin)):
        if not state.siren.available:
            return JSONResponse({"ok": False, "error": "buzzers not connected"}, status_code=409)
        import threading
        threading.Thread(target=state.siren.test, daemon=True).start()
        return JSONResponse({"ok": True, "message": "test beep sent"})

    @app.post("/api/camera/{camera}/{action}")
    async def camera_ctrl(camera: str, action: str, _user: str = Depends(auth.require_admin)):
        return JSONResponse({"ok": True, "camera": camera.lower(), "on": action in ("on", "enable")})

    # ── MJPEG streams ──────────────────────────────────────────────────────────
    @app.get("/stream")
    def stream(_user: str = Depends(auth.require_auth)):
        if not state.security:
            return JSONResponse({"error": "no security camera"}, status_code=404)
        return StreamingResponse(_mjpeg(state.security.latest_jpeg),
                                 media_type="multipart/x-mixed-replace; boundary=frame")

    @app.get("/farm_stream")
    def farm_stream(_user: str = Depends(auth.require_auth)):
        cam = state.farm_camera
        if not cam:
            return JSONResponse({"error": "no farm camera"}, status_code=404)

        def jpeg():
            import cv2
            ok, frame = cam.read()
            if not ok or frame is None:
                return None
            ok2, buf = cv2.imencode(".jpg", frame, [cv2.IMWRITE_JPEG_QUALITY, 70])
            return buf.tobytes() if ok2 else None

        return StreamingResponse(_mjpeg(jpeg), media_type="multipart/x-mixed-replace; boundary=frame")

    # ── storage / analytics ────────────────────────────────────────────────────
    @app.get("/api/storage")
    def storage_api(_user: str = Depends(auth.require_auth)):
        return JSONResponse({"events": list(state.events)})

    @app.get("/storage_img/{subpath:path}")
    def storage_img(subpath: str, _user: str = Depends(auth.require_auth)):
        from fastapi import HTTPException
        target = (config.STORAGE_DIR / subpath).resolve()
        root = config.STORAGE_DIR.resolve()
        if not str(target).startswith(str(root)) or not target.is_file():
            raise HTTPException(status_code=404)
        ext = target.suffix.lower()
        if ext not in _IMG_TYPES:
            raise HTTPException(status_code=404)
        return FileResponse(str(target), media_type=_IMG_TYPES[ext])

    @app.get("/api/analytics")
    def analytics(_user: str = Depends(auth.require_auth)):
        species: dict = {}
        for e in state.events:
            species[e["label"]] = species.get(e["label"], 0) + 1
        return JSONResponse({
            "moisture_history": state.irrigation.moisture_history(),
            "moisture_current": state.state_snapshot()["moisture"],
            "species_counts": species,
            "events": list(state.events)[:50],
        })

    @app.get("/img/{filename}")
    async def serve_image(filename: str):
        from fastapi import HTTPException
        target = (STATIC_DIR / Path(filename).name)
        if not target.is_file() or target.suffix.lower() not in _IMG_TYPES:
            raise HTTPException(status_code=404)
        return FileResponse(str(target), media_type=_IMG_TYPES[target.suffix.lower()])

    # ── FarmMonitor (live when attached) ───────────────────────────────────────
    @app.get("/api/farm_monitor/status")
    def fm_status(_user: str = Depends(auth.require_auth)):
        return JSONResponse(state.farm_status())

    @app.post("/api/farm_monitor/scan_now")
    def fm_scan(_user: str = Depends(auth.require_admin)):
        if state.farm_monitor is None:
            return JSONResponse({"ok": False, "error": "FarmMonitor not enabled"}, status_code=409)
        state.farm_monitor.request_scan()
        return JSONResponse({"ok": True, "message": "scan queued"})

    # ── FLORA (live when attached) ──────────────────────────────────────────────
    @app.get("/api/flora/schedule")
    def flora_schedule(_user: str = Depends(auth.require_auth)):
        if state.flora is None:
            return JSONResponse([])
        return JSONResponse(state.flora.list_tasks())

    @app.post("/api/flora/chat")
    async def flora_chat(body: dict, _user: str = Depends(auth.require_auth)):
        if state.flora is None:
            return JSONResponse({"reply": "FLORA is not enabled on this install.", "offline": True})
        reply = await asyncio.get_running_loop().run_in_executor(
            None, state.flora.chat, str(body.get("message", "")), _user)
        return JSONResponse({"reply": reply})

    # ── email notifications ─────────────────────────────────────────────────────
    @app.get("/api/notification_email")
    def notif_get(_user: str = Depends(auth.require_auth)):
        return JSONResponse({"configured": bool(state.notification_email),
                             "email": state.notification_email})

    @app.post("/api/notification_email")
    async def notif_set(data: dict, _user: str = Depends(auth.require_auth)):
        import re
        email = str(data.get("email", "")).strip()
        if not re.match(r"^[^@\s]+@[^@\s]+\.[^@\s]+$", email):
            return JSONResponse({"ok": False, "error": "Enter a valid email address"}, status_code=400)
        state.notification_email = email
        return JSONResponse({"ok": True, "email": email})

    return app
