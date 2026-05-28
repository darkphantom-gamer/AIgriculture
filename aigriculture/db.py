"""SQLite storage for users and login sessions.

The original ran on MySQL; this self-hosted build uses SQLite so a clone runs
with zero database setup (no server, no credentials, no extra container).
"""

from __future__ import annotations

import sqlite3
import time
from contextlib import contextmanager
from typing import Iterator, Optional

from . import config

DB_PATH = config.RUNTIME_DIR / "aigriculture.db"

_SCHEMA = """
CREATE TABLE IF NOT EXISTS users (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    username        TEXT UNIQUE NOT NULL,
    password_hash   TEXT NOT NULL,
    role            TEXT NOT NULL DEFAULT 'admin',
    display_name    TEXT,
    avatar_url      TEXT,
    failed_attempts INTEGER NOT NULL DEFAULT 0,
    locked_until    REAL,
    last_login      TEXT,
    created_at      TEXT DEFAULT CURRENT_TIMESTAMP
);
CREATE TABLE IF NOT EXISTS sessions (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    username    TEXT NOT NULL,
    jti         TEXT UNIQUE NOT NULL,
    issued_at   REAL NOT NULL,
    expires_at  REAL NOT NULL,
    revoked     INTEGER NOT NULL DEFAULT 0
);
CREATE INDEX IF NOT EXISTS idx_sessions_jti ON sessions(jti);
"""


@contextmanager
def connect() -> Iterator[sqlite3.Connection]:
    config.RUNTIME_DIR.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(DB_PATH, timeout=10, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    try:
        yield conn
        conn.commit()
    finally:
        conn.close()


def init_schema() -> None:
    with connect() as c:
        c.executescript(_SCHEMA)


# ── users ────────────────────────────────────────────────────────────────────
def count_users() -> int:
    with connect() as c:
        return int(c.execute("SELECT COUNT(*) AS n FROM users").fetchone()["n"])


def get_user(username: str) -> Optional[dict]:
    with connect() as c:
        row = c.execute("SELECT * FROM users WHERE username = ?", (username,)).fetchone()
        return dict(row) if row else None


def insert_user(username: str, password_hash: str, role: str = "admin",
                display_name: str = "", avatar_url: str = "") -> None:
    with connect() as c:
        c.execute(
            "INSERT OR IGNORE INTO users (username, password_hash, role, display_name, avatar_url) "
            "VALUES (?, ?, ?, ?, ?)",
            (username, password_hash, role, display_name or username, avatar_url),
        )


def set_failed(user_id: int, count: int, locked_until: Optional[float] = None) -> None:
    with connect() as c:
        c.execute("UPDATE users SET failed_attempts = ?, locked_until = ? WHERE id = ?",
                  (count, locked_until, user_id))


def record_login(user_id: int) -> None:
    with connect() as c:
        c.execute(
            "UPDATE users SET failed_attempts = 0, locked_until = NULL, last_login = ? WHERE id = ?",
            (time.strftime("%Y-%m-%d %H:%M:%S"), user_id),
        )


# ── sessions ───────────────────────────────────────────────────────────────
def create_session(username: str, jti: str, issued_at: float, expires_at: float) -> None:
    with connect() as c:
        c.execute(
            "INSERT INTO sessions (username, jti, issued_at, expires_at) VALUES (?, ?, ?, ?)",
            (username, jti, issued_at, expires_at),
        )


def revoke_session(jti: str) -> None:
    with connect() as c:
        c.execute("UPDATE sessions SET revoked = 1 WHERE jti = ?", (jti,))


def is_session_revoked(jti: str) -> bool:
    """True if the session is revoked OR unknown. Fails closed on any error."""
    try:
        with connect() as c:
            row = c.execute("SELECT revoked FROM sessions WHERE jti = ?", (jti,)).fetchone()
            return row is None or bool(row["revoked"])
    except Exception:
        return True
