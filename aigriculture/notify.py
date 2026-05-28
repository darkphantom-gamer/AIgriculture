"""Email notifications over SMTP.

All credentials come from config.yaml (smtp section) — see config.example.yaml.
Nothing is sent (and nothing errors) when SMTP isn't configured.
"""

from __future__ import annotations

import smtplib
import ssl
from email.message import EmailMessage
from pathlib import Path
from typing import List, Optional, Tuple


def smtp_ready(app_config: dict) -> bool:
    s = (app_config or {}).get("smtp", {})
    return bool(s.get("host") and s.get("email") and s.get("password"))


def send_email(app_config: dict, subject: str, body: str, to: Optional[str] = None,
               html: Optional[str] = None, attachments: Optional[List[str]] = None) -> Tuple[bool, str]:
    smtp = (app_config or {}).get("smtp", {})
    host, port = smtp.get("host"), int(smtp.get("port", 587))
    user, pw = smtp.get("email"), smtp.get("password")
    sender = smtp.get("from_email") or user
    recipient = to or (app_config.get("notifications", {}) or {}).get("to_email")
    if not (host and user and pw and recipient):
        return False, "SMTP not configured"

    msg = EmailMessage()
    msg["Subject"], msg["From"], msg["To"] = subject, sender, recipient
    msg.set_content(body)
    if html:
        msg.add_alternative(html, subtype="html")
    for path in attachments or []:
        p = Path(path)
        if p.is_file():
            msg.add_attachment(p.read_bytes(), maintype="image",
                               subtype=p.suffix.lstrip(".") or "jpeg", filename=p.name)
    try:
        with smtplib.SMTP(host, port, timeout=25) as server:
            server.starttls(context=ssl.create_default_context())
            server.login(user, pw)
            server.send_message(msg)
        return True, "sent"
    except Exception as e:
        return False, f"send failed: {e}"
