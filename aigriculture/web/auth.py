"""Authentication: bcrypt passwords, JWT cookie sessions, lockout + rate limit.

The default admin is seeded from the ADMIN_USER / ADMIN_PASS environment
variables on first run — there are no hard-coded credentials anywhere.
"""

from __future__ import annotations

import os
import secrets
import threading
import time
from typing import Optional
from urllib.parse import urlparse

import jwt
from fastapi import Depends, HTTPException, Request

from .. import config, db

JWT_ALGO = "HS256"
JWT_EXPIRE_HRS = int(os.getenv("AIGRI_JWT_EXPIRE_HRS", "8"))
MAX_ATTEMPTS = 5
LOCKOUT_SECS = 15 * 60
ADMIN_ROLE = "admin"
VIEWER_ROLE = "viewer"
COOKIE_NAME = "pmc_token"

NO_STORE_HEADERS = {
    "Cache-Control": "no-store, no-cache, must-revalidate, max-age=0",
    "Pragma": "no-cache",
    "Expires": "0",
}
SECURITY_HEADERS = {
    "X-Content-Type-Options": "nosniff",
    "X-Frame-Options": "DENY",
    "Referrer-Policy": "strict-origin-when-cross-origin",
    "Cross-Origin-Opener-Policy": "same-origin",
    "Permissions-Policy": "camera=(self), microphone=(), geolocation=()",
}


# ── secret + hashing ─────────────────────────────────────────────────────────
def _load_jwt_secret() -> str:
    env = os.getenv("JWT_SECRET", "").strip()
    if env:
        return env
    f = config.RUNTIME_DIR / ".jwt_secret"
    if f.exists():
        return f.read_text().strip()
    s = secrets.token_hex(48)
    try:
        config.RUNTIME_DIR.mkdir(parents=True, exist_ok=True)
        f.write_text(s)
        f.chmod(0o600)
    except Exception:
        pass  # fall back to an ephemeral secret (sessions reset on restart)
    return s


JWT_SECRET = _load_jwt_secret()


def hash_password(password: str) -> str:
    import bcrypt
    return bcrypt.hashpw(password.encode(), bcrypt.gensalt()).decode()


def verify_password(password: str, password_hash: str) -> bool:
    import bcrypt
    try:
        return bcrypt.checkpw(password.encode(), password_hash.encode())
    except Exception:
        return False


# ── credentials + tokens ─────────────────────────────────────────────────────
def verify_credentials(username: str, password: str) -> Optional[dict]:
    user = db.get_user(username)
    if not user:
        return None
    now = time.time()
    if user["locked_until"]:
        if now < float(user["locked_until"]):
            return None
        db.set_failed(user["id"], 0, None)  # lock expired
    if not verify_password(password, user["password_hash"]):
        count = int(user["failed_attempts"]) + 1
        locked = now + LOCKOUT_SECS if count >= MAX_ATTEMPTS else None
        db.set_failed(user["id"], count if not locked else 0, locked)
        return None
    db.record_login(user["id"])
    return user


def create_token(username: str) -> tuple[str, str]:
    jti = secrets.token_hex(32)
    now = time.time()
    exp = now + JWT_EXPIRE_HRS * 3600
    token = jwt.encode({"sub": username, "jti": jti, "exp": exp}, JWT_SECRET, algorithm=JWT_ALGO)
    db.create_session(username, jti, now, exp)
    return token, jti


def _decode(token: str) -> Optional[dict]:
    try:
        return jwt.decode(token, JWT_SECRET, algorithms=[JWT_ALGO])
    except (jwt.ExpiredSignatureError, jwt.InvalidTokenError):
        return None


def session_user(token: Optional[str]) -> Optional[str]:
    if not token:
        return None
    payload = _decode(token)
    if not payload or db.is_session_revoked(payload.get("jti", "")):
        return None
    return payload.get("sub")


# ── rate limiter (per-IP, in memory) ─────────────────────────────────────────
_rate_lock = threading.Lock()
_rate_map: dict[str, dict] = {}


def check_rate_limit(ip: str) -> bool:
    now = time.time()
    with _rate_lock:
        entry = _rate_map.get(ip, {"count": 0, "locked_until": 0})
        if entry["locked_until"] > now:
            return False
        if entry["locked_until"]:
            entry = {"count": 0, "locked_until": 0}
        entry["count"] += 1
        if entry["count"] > MAX_ATTEMPTS:
            entry = {"count": 0, "locked_until": now + LOCKOUT_SECS}
            _rate_map[ip] = entry
            return False
        _rate_map[ip] = entry
        return True


def reset_rate_limit(ip: str) -> None:
    with _rate_lock:
        _rate_map.pop(ip, None)


# ── headers ──────────────────────────────────────────────────────────────────
def request_scheme(request: Request) -> str:
    fwd = request.headers.get("x-forwarded-proto", "").split(",", 1)[0].strip().lower()
    return fwd or request.url.scheme


def is_https(request: Request) -> bool:
    return request_scheme(request) == "https"


def same_origin(request: Request, origin: Optional[str]) -> bool:
    if not origin:
        return True
    p = urlparse(origin)
    if not p.scheme or not p.netloc:
        return False
    return p.scheme == request_scheme(request) and p.netloc == request.headers.get("host", "")


def apply_security_headers(resp, request: Request):
    for k, v in SECURITY_HEADERS.items():
        resp.headers.setdefault(k, v)
    if is_https(request):
        resp.headers.setdefault("Strict-Transport-Security", "max-age=31536000; includeSubDomains")
    return resp


def no_store(resp):
    resp.headers.update(NO_STORE_HEADERS)
    return resp


# ── profile + permissions ─────────────────────────────────────────────────────
def get_user_profile(username: str) -> dict:
    profile = {"username": username or "", "role": ADMIN_ROLE,
               "display_name": username or "User", "avatar_url": ""}
    user = db.get_user(username) if username else None
    if user:
        profile.update({
            "username": user["username"],
            "role": user["role"] or ADMIN_ROLE,
            "display_name": user["display_name"] or user["username"],
            "avatar_url": user["avatar_url"] or "",
        })
    return profile


def user_permissions(role: str) -> dict:
    is_admin = role == ADMIN_ROLE
    return {
        "view": True, "email_signup": True,
        "control": is_admin, "irrigation": is_admin, "camera_actions": is_admin,
        "settings_write": is_admin, "flora_write": is_admin,
    }


def is_admin_user(username: str) -> bool:
    return get_user_profile(username).get("role") == ADMIN_ROLE


# ── FastAPI dependencies ─────────────────────────────────────────────────────
class AuthRedirect(Exception):
    """Raised on a failed browser (non-API) request to bounce to /login."""


async def require_auth(request: Request) -> str:
    token = request.cookies.get(COOKIE_NAME)
    is_api = request.url.path.startswith("/api") or request.url.path.startswith("/ws")
    user = session_user(token)
    if not user:
        if is_api:
            raise HTTPException(status_code=401, detail="Not authenticated")
        raise AuthRedirect()
    return user


async def require_admin(user: str = Depends(require_auth)) -> str:
    if not is_admin_user(user):
        raise HTTPException(status_code=403, detail="Admin account required for this action.")
    return user


def ensure_admin() -> None:
    """Seed the first admin from ADMIN_USER / ADMIN_PASS if no users exist.

    If ADMIN_PASS is missing we generate a strong random password and PRINT IT
    ONCE to the console — never falling back to a guessable default like "admin".
    """
    db.init_schema()
    if db.count_users() > 0:
        return
    username = os.getenv("ADMIN_USER", "admin").strip() or "admin"
    password = os.getenv("ADMIN_PASS", "").strip()
    generated = False
    if not password:
        password = secrets.token_urlsafe(16)
        generated = True
    db.insert_user(username, hash_password(password), role=ADMIN_ROLE, display_name=username)
    if generated:
        print("=" * 70)
        print(" FIRST-RUN ADMIN ACCOUNT  (ADMIN_PASS was not set in .env)")
        print(f"   username : {username}")
        print(f"   password : {password}")
        print(" Copy this NOW — it will not be shown again. Change it after login.")
        print("=" * 70, flush=True)
    else:
        print(f"[INFO] seeded admin user '{username}'")
