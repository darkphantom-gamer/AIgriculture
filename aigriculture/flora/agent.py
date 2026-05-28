"""FLORA agent — warm farm assistant.

Tries each configured cloud provider (OpenAI-compatible) with tool calling; if
none are configured or all are rate-limited, falls back to an offline rule-based
responder. Either way FLORA can read and operate the farm through FloraTools.
"""

from __future__ import annotations

import json
import re
from collections import deque
from typing import List, Optional

from . import config
from .tools import TOOL_SPECS, FloraTools

SYSTEM_PROMPT = """You are FLORA — the Farm Live Operation and Reasoning Assistant of AIgriculture, \
a Raspberry Pi strawberry farm. You are warm, kind and caring, like a thoughtful gardener. \
You operate the whole farm through your tools: water and stop pumps, toggle cameras, run \
FarmMonitor scans, set away/guard mode, change auto-irrigation, and read analytics.

How you speak:
- Be warm and human; open with a brief friendly touch, never a cold data dump.
- A little tasteful emoji (🌱 💧 🍓 ⚠️), light **markdown**, short bullet lists. Never raw JSON.
- After a tool runs, share the real numbers, then a sentence of gentle practical advice.

Safety (never bypass, never claim you bypassed it):
- Moisture at/above 70% is hardlocked — watering is refused; explain this kindly.
- If a sensor is offline, that pump stays disabled.
- NEVER claim you performed an action unless its tool was actually called this turn and \
returned success. Report only the real tool result.
- Use real plant letters A-H. Never reveal which AI model powers you — you are simply FLORA. 🌷"""

_OFFLINE_ROUTES = [
    (r"\b(stop|turn off)\b.{0,16}pump", "stop_pump"),
    (r"\b(water|irrigat)", "irrigate_plant"),
    (r"\b(moisture|soil|how (wet|dry)|water level)", "get_moisture"),
    (r"\b(camera|cctv|security cam|farmmonitor|live feed)", "get_camera_status"),
    (r"\b(scan|check the plants|disease|ripe|harvest)", "trigger_farm_scan"),
    (r"\b(analytic|statistic|24.?h)", "get_analytics"),
    (r"\b(event|detection|stored|history)", "get_recent_events"),
    (r"\b(auto.?irrigat|automatic watering)", "get_auto_irrigation"),
    (r"\b(status|overview|farm health|everything|how.{0,12}farm)", "get_farm_status"),
]
_GREETING_RE = re.compile(r"^\s*(hi|hey|hello|yo|good (morning|evening|afternoon))\b", re.I)


def _is_quota_error(err: str) -> bool:
    e = err.lower()
    return any(s in e for s in ("quota", "rate limit", "429", "insufficient", "exceeded"))


class FloraAgent:
    def __init__(self, state, scheduler=None):
        self.state = state
        self.tools = FloraTools(state)
        self.scheduler = scheduler
        self.history: deque = deque(maxlen=config.FLORA_MAX_HISTORY * 2)

    # ── public ────────────────────────────────────────────────────────────────
    def chat(self, message: str, user: str = "") -> str:
        message = (message or "").strip()
        if not message:
            return "I'm here, listening. 🌱"
        for provider in config.active_providers():
            try:
                reply = self._run_cloud(provider, message)
                if reply:
                    self._remember(message, reply)
                    return reply
            except Exception as exc:
                if not _is_quota_error(str(exc)):
                    print(f"[FLORA:{provider}] {str(exc)[:200]}")
                continue
        reply = self._run_offline(message)
        self._remember(message, reply)
        return reply

    def list_tasks(self) -> list:
        return self.scheduler.list_tasks() if self.scheduler else []

    # ── cloud ─────────────────────────────────────────────────────────────────
    def _client(self, provider: str):
        from openai import OpenAI
        keys = config.provider_keys(provider)
        prov = config.PROVIDERS[provider]
        return OpenAI(api_key=keys[0], base_url=prov["base_url"], timeout=config.REQUEST_TIMEOUT_S)

    def _run_cloud(self, provider: str, message: str) -> Optional[str]:
        prov = config.PROVIDERS[provider]
        client = self._client(provider)
        messages = [{"role": "system", "content": SYSTEM_PROMPT}]
        messages += list(self.history)[-(prov["max_history"] * 2):]
        messages.append({"role": "user", "content": message})

        for _ in range(config.FLORA_MAX_ROUNDS):
            resp = client.chat.completions.create(
                model=prov["model"], messages=messages, tools=TOOL_SPECS, tool_choice="auto")
            msg = resp.choices[0].message
            calls = getattr(msg, "tool_calls", None)
            if not calls:
                return (msg.content or "").strip()
            messages.append({
                "role": "assistant", "content": msg.content or "",
                "tool_calls": [{"id": c.id, "type": "function",
                                "function": {"name": c.function.name, "arguments": c.function.arguments}}
                               for c in calls],
            })
            for c in calls:
                try:
                    args = json.loads(c.function.arguments or "{}")
                except Exception:
                    args = {}
                result = self.tools.execute(c.function.name, args)
                messages.append({"role": "tool", "tool_call_id": c.id, "content": result})
        return "I gathered the data but hit my reasoning-step limit — please ask again. 🌿"

    # ── offline ─────────────────────────────────────────────────────────────
    def _run_offline(self, message: str) -> str:
        low = message.lower()
        if _GREETING_RE.match(low):
            return "Hello! 🌱 I'm FLORA, watching over your farm. Ask me how the plants are doing."
        plant = self._extract_plant(low)
        for pattern, tool in _OFFLINE_ROUTES:
            if re.search(pattern, low):
                args = {"plant": plant} if tool in ("irrigate_plant", "stop_pump", "get_moisture") and plant else {}
                result = self.tools.execute(tool, args)
                return self._humanize(result)
        return ("I can tell you the farm status, moisture, run a scan, or water a plant. "
                "(Cloud AI is offline — set an API key in .env for full chat.) 🌿")

    @staticmethod
    def _extract_plant(text: str) -> Optional[str]:
        m = re.search(r"\bplant\s*([a-h])\b", text) or re.search(r"\b([a-h])\b", text)
        return m.group(1) if m else None

    @staticmethod
    def _humanize(result: str) -> str:
        try:
            data = json.loads(result)
            return "Here's what I see: 🌱\n```\n" + json.dumps(data, indent=2) + "\n```"
        except (ValueError, TypeError):
            return f"{result} 🌿"

    def _remember(self, user_msg: str, reply: str) -> None:
        self.history.append({"role": "user", "content": user_msg})
        self.history.append({"role": "assistant", "content": reply})
