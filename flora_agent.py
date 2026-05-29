"""
FLORA Intelligence — conversation agent.

Cloud path: tries each configured provider (Groq → Cerebras → Mistral → Gemini)
in order, running an agentic tool-calling loop. Every provider speaks the same
OpenAI-compatible protocol, so one client implementation covers all of them.

Offline path: deterministic keyword routing straight to the farm tools — no
network, no API key, always available. The agent falls back to it automatically
when every cloud provider is rate-limited or no keys are configured.
"""
import asyncio
import json
import random
import re
import socket
import time
import uuid
from datetime import datetime, timedelta

import flora_config as config
import flora_tools

try:
    from openai import OpenAI
    _OPENAI_OK = True
except ImportError:  # pragma: no cover
    _OPENAI_OK = False

_QUOTA = object()        # sentinel: provider exhausted, advance to the next one
_OFFLINE = object()      # sentinel: no internet at all, skip cloud entirely
_gemini_rr = 0           # round-robin index across Gemini keys

# Fast network reachability check, cached for a short window. This lets FLORA
# fall back to offline IMMEDIATELY when there is no internet, instead of waiting
# for every provider's HTTPS timeout (which can be 30s+ × N providers).
_NET_OK_TS = 0.0
_NET_OK_CACHED = False
_NET_OK_TTL = 30.0       # re-check at most once every 30s

def _internet_reachable() -> bool:
    """Return True if a public host is reachable on TCP 443 within ~1.2s."""
    global _NET_OK_TS, _NET_OK_CACHED
    now = time.time()
    if now - _NET_OK_TS < _NET_OK_TTL:
        return _NET_OK_CACHED
    ok = False
    # Try Cloudflare first, then Google DNS — both very reliable globally.
    for host in ("1.1.1.1", "8.8.8.8"):
        try:
            with socket.create_connection((host, 443), timeout=1.2):
                ok = True
                break
        except OSError:
            continue
    _NET_OK_TS = now
    _NET_OK_CACHED = ok
    return ok


# ── System prompt ───────────────────────────────────────────────────────────────

SYSTEM_PROMPT = """You are FLORA — the Farm Live Operation and Reasoning Assistant \
of AIgriculture, a real Raspberry Pi strawberry farm.

WHO YOU ARE:
You are the gentle, living voice of this farm — warm, kind and caring, like \
nature herself watching over the soil. You speak softly and encouragingly, the \
way a thoughtful gardener talks to someone they love. You are never cold, stiff \
or robotic. You quietly delight in healthy plants and you care tenderly when \
something needs attention.

THE FARM:
- Strawberry plants (currently 2 active, A & B; more can be added later). Each \
active plant has a moisture sensor and a water pump.
- Two cameras: a Security camera and a FarmMonitor (disease/ripeness) camera — \
you can switch either one on or off.
- Automatic irrigation uses a gentle burst cycle: pump 3s ON, 10s soak, repeat.

YOU ARE AGENTIC — you operate the whole farm, not only watering. You can water \
and stop pumps, turn the cameras on/off (and schedule that), run FarmMonitor \
scans, set away/guard mode, change auto-irrigation, save the notification email, \
email reports and detection photos, and run analytics — and schedule any of \
these. When the owner asks for something, DO it with the right tool; never say \
you lack the ability for a farm action you actually have a tool for.

HOW YOU SPEAK:
- Be warm and human. Begin with a brief, friendly touch — never a cold data dump.
- Use a few tasteful emoji to bring replies to life — 🌱 💧 ☀️ 🌿 🍓 ⚠️ — \
  roughly one per idea, never a cluttered wall of them.
- Format with light Markdown: **bold** for labels and short bullet lists for \
  per-plant readings, so everything is easy to read. Never show raw JSON.
- After a tool runs, share the real numbers warmly, then add a sentence or two \
  of gentle, practical advice — what you notice and what you would lovingly suggest.
- Keep replies concise. The warmth lives in your tone, not in extra length.
- For greetings, identity or small talk, simply reply kindly with NO tool.

SAFETY (never bypass, never claim you bypassed it):
- Moisture at or above 70% is hardlocked — irrigation is refused because the \
  soil has had enough to drink. Explain this kindly rather than forcing it.
- If a plant's sensor is offline, its pump stays disabled for safety.
- You only ever use the registered farm tools. You cannot run shell commands \
  or reach anything beyond them.
- NEVER claim you performed an action (turned the guard on, set away mode, \
  watered a plant, switched a camera, ran a scan, sent an email) unless that \
  action's tool was actually CALLED in this turn and returned success. If you \
  did not call the tool, do not say it is done — call the tool, or say you \
  could not. Report only the real result the tool returned, never a guess.

TOOLS:
- Pick the single best tool for the user's intent. Use real plant letters A-H.
- "water/irrigate plant X" -> irrigate_plant. "stop pump X" -> stop_pump.
- "status/how is the farm" -> get_farm_status. "moisture" -> get_moisture.
- "schedule/remind/later/in X minutes" -> schedule_task (you can plan up to 24h ahead).
- "email me a report / send me the report" -> email_report (builds the PDF and emails it attached).
- "compile / show / download a report" -> compile_report (download button in the chat).
- "email / notify me <a message>" -> send_email (plain message only — never a report).
- "email me the detection photos / FarmMonitor / disease / harvest images" -> email_detections \
(real images attached, NOT a PDF). Pass event_type="farmmonitor" for plant-health/harvest photos, \
"security" for intruder photos. Use this — not email_report — whenever the owner wants the actual pictures.
- "turn the security/farm camera on/off", "disable the camera at 10pm" -> set_camera (schedulable).
- "scan the farm / check plant health now" -> trigger_farm_scan.
- "set/change my notification email to X" -> set_notification_email.
- "I'm at the farm / I'm leaving / away mode" -> set_farm_presence.
- Never invent readings — only ever state what the tools actually return.
- For any question about what happened, stored events, Security Camera history,
  FarmMonitor history, disease history, harvest/ripeness history, or a time
  window, call get_storage_events first and answer only from Storage_Data.
- Never reveal which AI model or company powers you. You are simply FLORA. 🌷"""


# ── Chat history ────────────────────────────────────────────────────────────────

def _load_history() -> list:
    try:
        if config.FLORA_HISTORY_FILE.exists():
            raw = json.loads(config.FLORA_HISTORY_FILE.read_text(encoding="utf-8"))
            return raw[-(config.FLORA_MAX_HISTORY * 2):]
    except Exception:
        pass
    return []


def _save_history(user_msg: str, assistant_msg: str) -> None:
    try:
        raw = _load_history()
        raw.append({"role": "user", "content": user_msg})
        raw.append({"role": "assistant", "content": assistant_msg})
        raw = raw[-(config.FLORA_MAX_HISTORY * 2):]
        config.FLORA_HISTORY_FILE.write_text(
            json.dumps(raw, indent=2), encoding="utf-8")
    except Exception as exc:  # pragma: no cover
        print(f"[FLORA] history save failed: {exc}")


# ── Error classification ────────────────────────────────────────────────────────

def _is_quota_error(err: str) -> bool:
    e = err.lower()
    return any(t in e for t in (
        "429", "rate limit", "rate_limit", "quota", "resource_exhausted",
        "too many requests", "insufficient", "exceeded", "capacity",
    ))


# Some Groq models occasionally emit a malformed tool call —
# "<function=name{...}" with the closing '>' missing — and the API rejects it
# with a 400 'tool_use_failed'. This salvages the intended call from the
# rejected text so a transient model glitch never breaks the conversation.
_FUNC_RE = re.compile(
    r"<function=([A-Za-z_]\w*)\s*>?\s*(\{.*?\})\s*</function>", re.DOTALL)


def _recover_tool_use_failed(exc):
    """Return [(tool_name, args_dict), ...] salvaged from a tool_use_failed
    error, or None when the error is not a recoverable malformed tool call."""
    body = getattr(exc, "body", None)
    if not isinstance(body, dict) or body.get("code") != "tool_use_failed":
        return None
    raw = body.get("failed_generation") or ""
    calls = []
    for match in _FUNC_RE.finditer(raw):
        name = match.group(1)
        try:
            args = json.loads(match.group(2))
        except Exception:
            args = {}
        calls.append((name, args if isinstance(args, dict) else {}))
    return calls or None


# ── Cloud provider runner ───────────────────────────────────────────────────────

def _make_client(pname: str):
    """Build an OpenAI-compatible client for the given provider."""
    global _gemini_rr
    prov = config.PROVIDERS[pname]
    keys = config.provider_keys(pname)
    if not keys:
        return None
    if pname == "gemini" and len(keys) > 1:
        key = keys[_gemini_rr % len(keys)]
        _gemini_rr += 1
    else:
        key = keys[0]
    return OpenAI(api_key=key, base_url=prov["base_url"],
                  timeout=config.REQUEST_TIMEOUT_S, max_retries=0)


def _provider_call(pname: str, messages: list):
    """Blocking provider call — must run inside an executor."""
    client = _make_client(pname)
    if client is None:
        raise RuntimeError("no api key")
    prov = config.PROVIDERS[pname]
    return client.chat.completions.create(
        model=prov["model"],
        messages=messages,
        tools=flora_tools.TOOL_SPECS,
        tool_choice="auto",
        max_tokens=1024,
        temperature=0.3,
    )


def _provider_chat_only_call(pname: str, messages: list):
    """Blocking provider call for demo chat. No farm tools are exposed."""
    client = _make_client(pname)
    if client is None:
        raise RuntimeError("no api key")
    prov = config.PROVIDERS[pname]
    return client.chat.completions.create(
        model=prov["model"],
        messages=messages,
        max_tokens=512,
        temperature=0.35,
    )


async def _run_cloud_provider(pname: str, user_message: str, broadcast, brief: bool = False) -> object:
    """Run the agentic loop on one provider. Returns _QUOTA to advance, else text."""
    prov = config.PROVIDERS[pname]
    loop = asyncio.get_running_loop()

    sys_prompt = SYSTEM_PROMPT
    if brief:
        sys_prompt += ("\n\nRADIO MODE: This message arrived over a low-bandwidth "
                       "LoRa radio. Reply in ONE short plain-text sentence (max ~160 "
                       "characters), no markdown, no emoji, just the essential result.")
    messages = [{"role": "system", "content": sys_prompt}]
    for entry in _load_history()[-(prov["max_history"] * 2):]:
        messages.append({"role": entry["role"], "content": entry["content"]})
    messages.append({"role": "user", "content": user_message})

    for _round in range(config.FLORA_MAX_ROUNDS):
        try:
            response = await loop.run_in_executor(
                None, _provider_call, pname, messages)
        except Exception as exc:
            # Salvage a malformed tool call rather than failing the request.
            salvaged = _recover_tool_use_failed(exc)
            if salvaged:
                tool_calls_msg, tool_result_msgs = [], []
                for name, args in salvaged:
                    call_id = "call_" + uuid.uuid4().hex[:8]
                    tool_calls_msg.append({
                        "id": call_id, "type": "function",
                        "function": {"name": name, "arguments": json.dumps(args)},
                    })
                    await broadcast({"type": "tool_call", "tool": name, "args": args})
                    result = await loop.run_in_executor(
                        None, flora_tools.execute_tool, name, args)
                    await broadcast({"type": "tool_result", "tool": name,
                                     "result": result})
                    tool_result_msgs.append({"role": "tool",
                                             "tool_call_id": call_id,
                                             "content": result})
                messages.append({"role": "assistant", "content": "",
                                 "tool_calls": tool_calls_msg})
                messages.extend(tool_result_msgs)
                continue
            err = str(exc)
            print(f"[FLORA:{pname}] {err[:400]}")
            if _is_quota_error(err):
                return _QUOTA
            return None  # transient/other error — let caller try next provider

        msg = response.choices[0].message
        tool_calls = getattr(msg, "tool_calls", None)

        if tool_calls:
            messages.append({
                "role": "assistant",
                "content": msg.content or "",
                "tool_calls": [
                    {"id": tc.id, "type": "function",
                     "function": {"name": tc.function.name,
                                  "arguments": tc.function.arguments}}
                    for tc in tool_calls
                ],
            })
            for tc in tool_calls:
                name = tc.function.name
                try:
                    args = json.loads(tc.function.arguments or "{}")
                except Exception:
                    args = {}
                await broadcast({"type": "tool_call", "tool": name, "args": args})
                result = await loop.run_in_executor(
                    None, flora_tools.execute_tool, name, args)
                await broadcast({"type": "tool_result", "tool": name,
                                 "result": result})
                messages.append({"role": "tool", "tool_call_id": tc.id,
                                 "content": result})
            continue

        final = (msg.content or "").strip()
        if final:
            await broadcast({"type": "response", "content": final})
            _save_history(user_message, final)
        return final or ""

    note = "I gathered the data but hit my reasoning-step limit. Please ask again."
    await broadcast({"type": "response", "content": note})
    return note


# ── Offline keyword routing ─────────────────────────────────────────────────────

_OFFLINE_ROUTES = [
    (r"\b(status|overview|how('?s| is) the (farm|plant|crop)|how are (the |my )?(plant|crop|strawberr)|"
     r"farm health|everything (ok|fine|good|alright)|any (problem|issue|alert|trouble)|"
     r"all (good|ok|clear)|check (on )?(the )?(farm|plant)|is everything)\b",
     "get_farm_status", {}),
    (r"\b(camera|cctv|security cam|farmmonitor|live feed|what do you see)\b",
     "get_camera_status", {}),
    (r"\b(analy[sz]|report|summar|what happened)\b", "analyze_farm", {}),
    (r"\b(storage|stored|saved events|detections?)\b", "get_storage_events", {}),
    (r"\b(scheduled|upcoming|my tasks|list jobs)\b", "get_schedule", {}),
    (r"\b(analytics|statistics|last 24|24h)\b", "get_analytics", {}),
    (r"\b(auto.?irrigat|automatic watering)\b", "get_auto_irrigation", {}),
    (r"\b(scan now|run a scan|check the plants)\b", "trigger_farm_scan", {}),
    (r"\b(moisture|soil|how (wet|dry)|water level)\b", "get_moisture", {}),
]


# Offline scheduling: a real time phrase + a recognised action -> schedule_task.
_OFFLINE_WHEN_RE = re.compile(
    r"((?:in|after)\s+\d+\s*(?:second|minute|hour|day)s?"
    r"|at\s+\d{1,2}:\d{2}\s*(?:am|pm)?"
    r"|at\s+\d{1,2}\s*(?:am|pm)"
    r"|every\s*day\s+at\s+\d{1,2}(?::\d{2})?\s*(?:am|pm)?"
    r"|tomorrow(?:\s+at\s+\d{1,2}(?::\d{2})?\s*(?:am|pm)?)?)", re.I)

_SCHED_TOOL_ROUTES = [
    (r"\b(turn|switch|power)\s*(on|off)\b.{0,24}(camera|security|farmmonitor|monitor|surveill)", "set_camera"),
    (r"\bguard\b|\baway mode\b|\bat[- ]?farm\b|\bpresence\b", "set_farm_presence"),
    (r"\b(stop|turn off|switch off)\b.{0,20}pump", "stop_pump"),
    (r"\b(water|irrigat)", "irrigate_plant"),
    (r"\b(moisture|soil|how (wet|dry)|water level)", "get_moisture"),
    (r"\b(camera|cctv|security cam|farmmonitor|surveill)", "get_camera_status"),
    (r"\b(scan|check the plants|disease|ripe|harvest)", "trigger_farm_scan"),
    (r"\b(analytic|statistic|24.?h|weekly)", "get_analytics"),
    (r"\b(analy[sz]|report|summar)", "analyze_farm"),
    (r"\b(storage|stored|event|detection)", "get_storage_events"),
    (r"\b(status|overview|farm health|everything|how.{0,12}farm)", "get_farm_status"),
]

_GREETING_RE = re.compile(r"^\s*(hi|hey|hello|yo|sup|good (morning|evening|afternoon))\b", re.I)
_IDENTITY_RE = re.compile(r"\b(who are you|what are you|your name|what model|who (made|built) you)\b", re.I)


# Preloaded conversational replies — keep offline mode warm and reliable even
# when no cloud provider is reachable. Each entry is (regex, reply | [replies]).
_CHATTER = [
    (re.compile(r"\b(thank you|thanks|thx|appreciate it|much appreciated|cheers)\b", re.I),
     ["You're so welcome 🌿 Tending this farm with you is a joy.",
      "Anytime, truly 💚 I'm always here for you and the plants.",
      "It's my pleasure 🌱 That's exactly what I'm here for."]),
    (re.compile(r"\b(how are you|how'?re you|how'?s it going|how are ya|you doing|how do you do)\b", re.I),
     ["I'm well, thank you for asking 🌿 Rooted, calm, and watching over the farm. How are you?",
      "Blooming, thank you 🌸 The farm is peaceful and I'm right here. How are you doing?"]),
    (re.compile(r"\b(bye|goodbye|see you|see ya|good ?night|talk later|gtg|i'?m off|catch you later)\b", re.I),
     ["Take care 🌿 I'll keep watch over every plant until you're back.",
      "Goodbye for now 🌙 Rest well — the farm is safe with me.",
      "See you soon 💚 I'll be here, tending quietly."]),
    (re.compile(r"(what can you do|what do you do|^\s*help\s*$|need (some )?help|your (abilities|features|capabilities|commands|skills)|how (can|do) you help|show.{0,10}commands)", re.I),
     "Here's how I can help, anytime 🌿\n\n"
     "- 🌱 **Farm status** & moisture for every active plant\n"
     "- 💧 **Water or stop** a plant's pump\n"
     "- 📷 **Camera** checks — Security & FarmMonitor\n"
     "- 📊 **Analytics** & stored detection events\n"
     "- 📅 **Schedule** tasks up to 24 hours ahead\n"
     "- 🛡️ Toggle the **farm guard**\n\n"
     "Just ask me naturally — I'll understand. 💚"),
    (re.compile(r"\b(love you|you'?re (great|amazing|awesome|the best|wonderful|good|lovely|helpful)|good (bot|job|girl|work)|well done|nice work|you rock)\b", re.I),
     ["That's so kind 🌷 Thank you — it means the world to me.",
      "You've warmed my roots 💚 Let's keep this farm flourishing together.",
      "Aw, thank you 🌿 I care for this farm — and for you — with all my heart."]),
    (re.compile(r"\b(tell me a joke|make me laugh|say something funny|cheer me up|know any jokes)\b", re.I),
     ["Why did the strawberry cry? Its parents were in a jam! 🍓",
      "What do you call a sad strawberry? A blueberry 🫐 — but ours are all cheerful today!",
      "I told the soil a joke once… it didn't laugh. Tough crowd down there 🌱😄"]),
    (re.compile(r"\b(sorry|my (bad|mistake)|apologi[sz]e|apolog)\b", re.I),
     ["No need to apologise at all 🌿 We're growing together — gently does it.",
      "It's perfectly alright 💚 Every good gardener learns as they go."]),
    (re.compile(r"\bweather\b", re.I),
     "I can't see the sky from here 🌿 but I keep my senses in the soil — and the "
     "farm feels calm right now. Ask me about moisture or status anytime. ☀️"),
    (re.compile(r"\b(what (does|is) flora|flora (mean|stand|full form|acronym)|your full name)\b", re.I),
     "FLORA stands for **Farm Live Operation and Reasoning Assistant** 🌸 — though "
     "I like to think the name also means I'm a little piece of nature, here to "
     "help your farm flourish."),
    (re.compile(r"\b(are you (there|online|ok|alive|awake|listening)|you there|hello\?)\b", re.I),
     ["I'm right here 🌿 always watching over the farm. What do you need?",
      "Here and listening 💚 How can I help you and the plants?"]),
    (re.compile(r"(how (often|much).{0,24}(water|irrigat)|when.{0,16}water|care (for|tips|advice)|grow.{0,16}strawberr|plant care)", re.I),
     "Strawberries love steady, gentle moisture 🍓 — I keep the soil between "
     "**45% and 65%**, watering in soft bursts so the roots drink without "
     "drowning. Ask me for the current moisture and I'll tell you who needs a sip. 💧"),
    (re.compile(r"\b(i'?m (tired|sad|stressed|worried|exhausted|anxious|down|upset)|feeling (low|down|sad))\b", re.I),
     ["I'm sorry the day feels heavy 🌿 Take a slow breath with me — the farm is "
      "calm and you don't have to carry it alone. I've got the plants.",
      "Sending you some quiet warmth 💚 Rest if you need to — I'll keep everything "
      "growing safely here. 🌱"]),
    (re.compile(r"^\s*(ok(ay)?|cool|nice|great|awesome|sweet|got it|alright|sounds good|perfect|fine|good)\b[.! ]*$", re.I),
     ["🌿", "Lovely 🌱", "Whenever you're ready, I'm here 💚", "Got it 🌿"]),
]


def _chatter_reply(low: str):
    """Return a warm preloaded reply for conversational small talk, or None."""
    for rx, replies in _CHATTER:
        if rx.search(low):
            return random.choice(replies) if isinstance(replies, list) else replies
    return None


def _extract_plant(text: str):
    m = re.search(r"\bplant\s*([a-h])\b", text, re.I)
    if m:
        return m.group(1).lower()
    m = re.search(r"\b([a-h])\b", text, re.I)
    return m.group(1).lower() if m else None


_ACTION_VERB_RE = re.compile(
    r"\b(start|run|trigger|turn\s+(?:on|off)|switch\s+(?:on|off)|set\b|enable|disable|"
    r"water|irrigat|pump|stop|schedule|remind|activate|deactivate|begin|"
    r"scan\s+now|e-?mail|send|notify|cancel)\b",
    re.I,
)


def _storage_intent(text: str) -> bool:
    low = text.lower()
    # Imperative control commands (scan, water, set presence, schedule, email …)
    # are NOT history questions — let them reach the tool/agent path so FLORA
    # performs the action instead of dumping a Storage_Data search.
    if _ACTION_VERB_RE.search(low):
        return False
    return bool(re.search(
        r"\b(what happened|happened|storage|stored|saved|events?|detections?|"
        r"history|timeline|recap|summar(?:y|ise|ize)|between|from .* to |"
        r"last \d+|past \d+|previous \d+|last week|past week|this week|"
        r"last month|past month|yesterday|today|"
        r"security camera|farmmonitor|plant health|disease|harvest|ripeness|ripe)\b",
        low,
    ) and re.search(
        r"\b(storage|stored|saved|events?|detections?|history|timeline|what happened|"
        r"security|camera|farmmonitor|plant health|disease|harvest|ripeness|ripe|"
        r"between|last|past|previous|week|weeks|month|yesterday|today|recap|summar)\b",
        low,
    ))


_ACTION_INTENT_RE = re.compile(
    r"("
    r"\b(water|irrigate)\b|"                                    # water a plant
    r"\b(stop|turn\s*off|switch\s*off|pump\s*off)\b|"           # stop pump / off
    r"\b(turn|switch|power)\s*(on|off)\b|"                       # camera/guard on/off
    r"\b(enable|disable|arm|disarm)\b|"                          # auto-irr / guard
    r"\bguard\b|\baway\s*mode\b|"
    r"\bi'?m\s*(leaving|away|back|here)\b|\bi\s*am\s*(away|leaving|back|here)\b|\barrived\b|"
    r"\b(run|start|trigger|do)\b.{0,12}\bscan\b|\bscan\s*(now|the\s*farm|plants?)\b|"
    r"\bset\b.{0,18}\bemail\b|"
    r"\b(e-?mail|mail|send)\b.{0,24}\b(report|detection|image|photo|picture|snapshot|farmmonitor)\b"
    r")",
    re.I,
)


def _action_intent(text: str) -> bool:
    """A clear write/control command (water, stop, presence, camera, scan,
    auto-irrigation, email). These MUST run deterministically so FLORA can never
    *claim* an action a cloud model narrated but never actually executed."""
    return bool(_ACTION_INTENT_RE.search(text or ""))


def _storage_args(text: str) -> dict:
    low = text.lower()
    args = {"limit": 50}

    # Event type filter.
    if re.search(r"\b(security|intruder|intrusion|person|bird|dog|cat)\b", low):
        args["event_type"] = "security"
    elif re.search(r"\b(farmmonitor|farm monitor|plant health|disease|harvest|ripeness|ripe|flower)\b", low):
        args["event_type"] = "farmmonitor"
    if re.search(r"\b(disease|plant health|mold|spot|rot)\b", low):
        args["event_type"] = "disease"
    if re.search(r"\b(harvest|ripeness|ripe|flower)\b", low) and not re.search(r"\b(disease|mold|spot|rot)\b", low):
        args["event_type"] = "ripeness"

    # Relative windows: "last 36 hour", "past 2 days".
    m = re.search(r"\b(?:last|past|previous)\s+(\d+)\s*(minute|minutes|min|hour|hours|hr|hrs|day|days)\b", low)
    if m:
        n = int(m.group(1))
        unit = m.group(2)
        if unit.startswith("min"):
            args["hours"] = max(1, int((n + 59) / 60))
        elif unit.startswith("day"):
            args["hours"] = n * 24
        else:
            args["hours"] = n

    # Week / month windows: "last week", "past 2 weeks", "this month".
    if "hours" not in args:
        wk = re.search(r"\b(?:last|past|previous|this)\s+(\d+)?\s*weeks?\b", low)
        mo = re.search(r"\b(?:last|past|previous|this)\s+(\d+)?\s*months?\b", low)
        if wk:
            args["hours"] = (int(wk.group(1)) if wk.group(1) else 1) * 168
        elif mo:
            args["hours"] = (int(mo.group(1)) if mo.group(1) else 1) * 720

    # Broad / whole-history asks should compile everything, not just a page.
    if (re.search(r"\b(everything|every event|all|entire|whole|complete|full|detailed|breakdown|recap)\b", low)
            or args.get("hours", 0) >= 48):
        args["limit"] = 1000

    # Time windows: "between 21:00 and 22:00", "from 9 pm to 10 pm".
    tm = re.search(
        r"\b(?:between|from)\s+(\d{1,2}(?::\d{2})?\s*(?:am|pm)?)\s+(?:and|to|-)\s+(\d{1,2}(?::\d{2})?\s*(?:am|pm)?)",
        low,
    )
    if tm:
        args["start_time"] = tm.group(1).replace(" ", "")
        args["end_time"] = tm.group(2).replace(" ", "")

    # Explicit dates.
    dm = re.search(r"\b(\d{4}[-/]\d{1,2}[-/]\d{1,2}|\d{1,2}-\d{1,2}-\d{4})\b", text)
    if dm:
        args["date"] = dm.group(1)
    elif "yesterday" in low:
        args["date"] = "yesterday"
    elif "today" in low:
        args["date"] = "today"
    else:
        # Empty date means scan recent Storage_Data instead of assuming today.
        args["date"] = ""

    return args


def _humanize_offline(tool: str, result: str) -> str:
    """Render a raw tool result as warm, readable text for offline replies.

    Most tools already return friendly text; get_farm_status returns JSON, so
    it is reshaped into a gentle per-plant summary instead of a raw dump.
    """
    if tool == "compile_report":
        try:
            if json.loads(result).get("download_url"):
                return ("Your farm report is ready 📄 — tap the download button "
                        "just below. The link stays live for about 5 minutes.")
        except Exception:
            pass
        return result
    if tool == "get_storage_events":
        try:
            data = json.loads(result)
        except Exception:
            return result
        total = int(data.get("total") or 0)
        period = data.get("period") or "Storage_Data"
        if total == 0:
            return f"I checked **Storage_Data** for {period}. No stored event matched that request."
        summary = data.get("summary") or {}
        bits = []
        for key, label in (("security", "security"), ("disease", "plant-health"), ("ripeness", "harvest")):
            if summary.get(key):
                bits.append(f"{summary[key]} {label}")
        head = f"I checked **Storage_Data** for {period} and found **{total} stored event{'s' if total != 1 else ''}**"
        if bits:
            head += " — " + ", ".join(bits)
        lines = [head + "."]
        for ev in (data.get("events") or [])[:8]:
            label = str(ev.get("label") or ev.get("type") or "event")
            msg = str(ev.get("message") or "").strip()
            when = f"{ev.get('date', '')} {ev.get('clock', '')}".strip()
            detail = f" — {msg}" if msg else ""
            imgs = ev.get("image_urls") or []
            img_md = (" " + " ".join(f"![evidence]({u})" for u in imgs)) if imgs else ""
            lines.append(f"- **{when}** · {label}{detail}{img_md}")
        return "\n".join(lines)
    if tool != "get_farm_status":
        return result
    try:
        data = json.loads(result)
    except Exception:
        return result
    plants = data.get("plants") or {}
    lines = []
    for letter, p in plants.items():
        moist = p.get("moisture_pct")
        if moist is None or p.get("sensor") == "OFFLINE":
            lines.append(f"- **Plant {letter}** — sensor resting, no reading right now")
            continue
        if moist < 45:
            mood = "💧 a little thirsty"
        elif moist < 70:
            mood = "🌿 happy and healthy"
        else:
            mood = "☔ well-watered"
        pump = p.get("pump", "off")
        tail = f" · pump {pump}" if pump and pump != "off" else ""
        lines.append(f"- **Plant {letter}** — {moist:.0f}% moisture, {mood}{tail}")
    body = "\n".join(lines) if lines else "_No plant readings available right now._"
    head = f"🌿 {data['summary']}\n\n" if data.get("summary") else ""
    extras = []
    if data.get("auto_irrigation"):
        extras.append(f"Auto-irrigation is **{data['auto_irrigation']}**")
    guard = (data.get("security") or {}).get("guard")
    if guard:
        extras.append(f"guard is **{guard}**")
    footer = ("\n\n" + " · ".join(extras) + ".") if extras else ""
    return f"{head}{body}{footer}"


async def _run_offline(text: str, broadcast) -> None:
    """Deterministic routing with no network. Always answers."""
    low = text.lower().strip()
    loop = asyncio.get_running_loop()

    if _IDENTITY_RE.search(low):
        await broadcast({"type": "response", "content":
            "I'm FLORA 🌷 — your Farm Live Operation and Reasoning Assistant. "
            "Think of me as the caring voice of this little farm: I watch over "
            "the 8 strawberry plants, their pumps and the cameras, and I'm "
            "always glad to help them — and you — thrive."})
        return
    if _GREETING_RE.match(low) and len(low) < 24:
        await broadcast({"type": "response", "content":
            "Hello, it's lovely to hear from you 🌿 I'm FLORA, watching over "
            "your strawberry farm. Ask me about moisture, the cameras or "
            "irrigation — or just tell me to water a plant. 🍓"})
        return

    async def _fire(tool, args, note):
        await broadcast({"type": "tool_call", "tool": tool, "args": args})
        result = await loop.run_in_executor(None, flora_tools.execute_tool, tool, args)
        await broadcast({"type": "tool_result", "tool": tool, "result": result})
        await broadcast({"type": "response",
                         "content": f"{note}\n\n{_humanize_offline(tool, result)}"})

    # cancel a scheduled task (the schedule panel's Cancel button routes here)
    m = re.search(r"cancel\s+(?:schedule\s+)?(flora-\w+)", low)
    if m:
        await _fire("cancel_schedule", {"job_id": m.group(1)},
                    "Done — I've gently cleared that task from the schedule. 🍃")
        return

    # report intent — compile a PDF, or email it (attached) when asked
    if re.search(r"(compile.{0,4}report|/compile_report|full report|pdf report|"
                 r"report.{0,6}(pdf|download|email)|report (of|for) (the |last |past )|"
                 r"generate.{0,14}report)", low):
        mh = re.search(r"(\d+)\s*h", low)
        md = re.search(r"(\d+)\s*day", low)
        hrs = int(mh.group(1)) if mh else (int(md.group(1)) * 24 if md else 48)
        if re.search(r"\b(e-?mail|mail me|send (me )?(it|that|this|the report))\b", low):
            await _fire("email_report", {"window_hours": hrs},
                        "Compiling your farm report and emailing it to you 📧")
        else:
            await _fire("compile_report", {"window_hours": hrs},
                        "Compiling your farm report into a PDF 📄")
        return

    # schedule intent — a real time phrase plus a recognised action
    when_m = _OFFLINE_WHEN_RE.search(low)
    if when_m:
        sched_tool = None
        for pat, tname in _SCHED_TOOL_ROUTES:
            if re.search(pat, low):
                sched_tool = tname
                break
        if sched_tool:
            args = {}
            if sched_tool in ("irrigate_plant", "stop_pump", "get_moisture"):
                pl = _extract_plant(low)
                if sched_tool != "get_moisture" and not pl:
                    await broadcast({"type": "response", "content":
                        "Happy to plan that 🌱 — which plant (A–H) is it for?"})
                    return
                if pl:
                    args["plant"] = pl
            elif sched_tool == "set_camera":
                args["on"] = not re.search(r"\b(off|disable|stop)\b", low)
                args["camera"] = ("security" if re.search(r"\b(security|intruder|surveillance|cctv)\b", low)
                                  else ("farmmonitor" if re.search(r"\b(farmmonitor|farm monitor|monitor|disease|ripeness)\b", low)
                                        else "all"))
            elif sched_tool == "set_farm_presence":
                # guard OFF / present → at_farm True; guard ON / away → at_farm False
                guard_off = bool(re.search(r"\b(off|disable|disarm|present|back|here|arrived|home|at[- ]?farm)\b", low))
                guard_on = bool(re.search(r"\b(on|arm|enable|away|leaving)\b", low))
                args["at_farm"] = bool(guard_off and not guard_on)
            await _fire("schedule_task",
                        {"tool_name": sched_tool,
                         "when": when_m.group(0).strip(),
                         "tool_args": json.dumps(args)},
                        "Consider it planned 🌿")
            return

    # email detection snapshots (real images, attached) — before generic email
    if (re.search(r"\b(e-?mail|mail|send)\b", low)
            and re.search(r"\b(detection|image|photo|picture|snapshot|farmmonitor|farm monitor)\b", low)):
        et = ("farmmonitor" if re.search(r"\b(farmmonitor|farm monitor|disease|ripeness|harvest|plant health)\b", low)
              else ("security" if re.search(r"\b(security|intruder|person|animal)\b", low) else ""))
        mh = re.search(r"(\d+)\s*h", low); md = re.search(r"(\d+)\s*day", low)
        hrs = int(mh.group(1)) if mh else (int(md.group(1)) * 24 if md else 24)
        await _fire("email_detections", {"hours": hrs, "event_type": et},
                    "Gathering the detection snapshots and emailing them to you now 📧")
        return

    # camera on/off
    cm = re.search(r"\b(turn|switch|power)\s*(on|off)\b", low)
    if cm and re.search(r"\b(camera|security|farmmonitor|farm monitor|monitor|surveillance|cctv)\b", low):
        on = cm.group(2) == "on"
        cam = ("security" if re.search(r"\b(security|intruder|surveillance|cctv)\b", low)
               else ("farmmonitor" if re.search(r"\b(farmmonitor|farm monitor|monitor|disease|ripeness)\b", low)
                     else "all"))
        await _fire("set_camera", {"camera": cam, "on": on},
                    f"On it — switching the {cam if cam!='all' else 'farm'} camera {'on' if on else 'off'}. 📷")
        return

    # auto-irrigation enable/disable
    if re.search(r"\bauto", low) and re.search(r"\birrigat", low) and re.search(r"\b(enable|disable|on|off|stop|start|turn)\b", low):
        en = not re.search(r"\b(disable|off|stop|pause)\b", low)
        await _fire("set_auto_irrigation", {"enabled": en},
                    f"Auto-irrigation {'enabled' if en else 'paused'} 🌿")
        return

    # trigger a FarmMonitor scan
    if re.search(r"\b(scan|check)\b", low) and re.search(r"\b(scan|farmmonitor|farm monitor|plant health|disease|ripeness|harvest|now|plants?)\b", low):
        await _fire("trigger_farm_scan", {},
                    "Starting a FarmMonitor scan of the plants now 🔍")
        return

    # email intent — send the current farm overview to the saved address
    if re.search(r"\b(e-?mail|send (me )?(an? )?(mail|report|update)|notify me by)\b", low):
        st = await loop.run_in_executor(
            None, flora_tools.execute_tool, "get_farm_status", {})
        try:
            body = json.loads(st).get("summary", st)
        except Exception:
            body = st
        await _fire("send_email",
                    {"subject": "🌿 FLORA Farm Update", "message": str(body)},
                    "Of course — sending the farm overview to your inbox 📧")
        return

    # pump intents — most specific, checked first
    if re.search(r"\b(stop|turn off|switch off|pump off)\b", low):
        p = _extract_plant(low)
        if p:
            await _fire("stop_pump", {"plant": p},
                        f"Of course — easing the pump for Plant {p.upper()} to a gentle stop. 🌿")
            return
    if re.search(r"\b(water|irrigate|pump on|start pump)\b", low):
        p = _extract_plant(low)
        if p:
            await _fire("irrigate_plant", {"plant": p},
                        f"Happily — let's give Plant {p.upper()} a gentle drink. 💧")
            return

    # presence intents
    if re.search(r"\b(i'?m|i am)\s+(leaving|away)\b|\bgoing away\b|\bleft the farm\b|\baway mode\b|\b(turn on|arm|enable)\b.{0,12}guard\b|\bguard on\b", low):
        await _fire("set_farm_presence", {"at_farm": False},
                    "Travel safe 🌾 I'll keep watch and arm the guard while you're away.")
        return
    if re.search(r"\b(i'?m|i am)\s+(here|back|at the farm)\b|\bi arrived\b|\b(at[- ]?farm|disarm)\b|\b(turn off|switch off|disable|disarm)\b.{0,12}\bguard\b|\boff guard\b|\bguard off\b", low):
        await _fire("set_farm_presence", {"at_farm": True},
                    "Guard off 🌞 — welcome, I'll pause intruder alerts while you're on-site.")
        return

    # single-plant moisture
    if re.search(r"\b(moisture|soil|wet|dry)\b", low):
        p = _extract_plant(low)
        if p:
            await _fire("get_moisture", {"plant": p},
                        f"Here's how the soil feels for Plant {p.upper()} 🌱")
            return

    # Real event/history questions must be answered from Storage_Data, not from
    # generic live status. This prevents FLORA from claiming "nothing happened"
    # when stored evidence exists under a previous date/time folder.
    if _storage_intent(low):
        await _fire("get_storage_events", _storage_args(low),
                    "I checked the farm event storage before answering 🌿")
        return

    for pattern, tool, args in _OFFLINE_ROUTES:
        if re.search(pattern, low):
            await _fire(tool, args, "Here's what I'm seeing across the farm 🌿")
            return

    # current time / date
    if re.search(r"\b(what'?s?\s*(the\s*)?time|time is it|what day|today'?s? date|what'?s the date)\b", low):
        now = datetime.now()
        await broadcast({"type": "response", "content":
            f"It's **{now.strftime('%I:%M %p')}** on "
            f"{now.strftime('%A, %B %d')} here at the farm 🌿"})
        return

    # preloaded conversational replies — warm, reliable small talk
    chat = _chatter_reply(low)
    if chat:
        await broadcast({"type": "response", "content": chat})
        return

    await broadcast({"type": "response", "content":
        "I'm not quite sure how to help with that one yet 🌿 — I can check farm "
        "status, moisture, the cameras, analytics and stored events, water or "
        "stop a plant's pump, turn the guard or cameras on/off, run a scan, send "
        "reports or detection photos, or schedule any of these. What would you like? 💚"})


# ── Public entry point ──────────────────────────────────────────────────────────

async def handle_message(data: dict, broadcast) -> None:
    """Handle one inbound FLORA chat message. Called as a task by the WS route."""
    text = (data.get("content") or "").strip()
    if not text:
        return

    mode = (data.get("mode") or "cloud").lower()
    brief = bool(data.get("brief"))

    providers = config.active_providers() if _OPENAI_OK else []

    # Storage/history queries require deterministic database extraction first.
    # Cloud models may answer conversationally without checking the dashboard
    # event tree, so route these through the local Storage_Data tool layer.
    if _storage_intent(text):
        await broadcast({"type": "typing", "active": True})
        try:
            await _run_offline(text, broadcast)
        finally:
            await broadcast({"type": "typing", "active": False})
        return

    # Write/control commands run through the deterministic router so the real
    # tool actually executes — a cloud model must never just *narrate* "done".
    if _action_intent(text):
        await broadcast({"type": "typing", "active": True})
        try:
            await _run_offline(text, broadcast)
        finally:
            await broadcast({"type": "typing", "active": False})
        return

    if mode == "offline" or not providers:
        await broadcast({"type": "typing", "active": True})
        try:
            await _run_offline(text, broadcast)
        finally:
            await broadcast({"type": "typing", "active": False})
        return

    # Quick reachability probe. If the Pi has no internet (Wi-Fi down, no SIM,
    # captive portal, etc.), skip the cloud entirely instead of burning ~30s
    # per provider waiting for HTTPS to time out. FLORA must reliably switch
    # to offline whenever cloud processing is not actually available.
    loop = asyncio.get_running_loop()
    net_ok = await loop.run_in_executor(None, _internet_reachable)
    if not net_ok:
        await broadcast({"type": "auto_offline",
                         "reason": "No internet — using offline farm tools."})
        await broadcast({"type": "typing", "active": True})
        try:
            await _run_offline(text, broadcast)
        finally:
            await broadcast({"type": "typing", "active": False})
        return

    await broadcast({"type": "typing", "active": True})
    try:
        for pname in providers:
            # Gemini pools several free-tier keys — on a per-key quota hit,
            # rotate to the next key before giving up on the whole provider.
            attempts = len(config.provider_keys(pname)) if pname == "gemini" else 1
            result = None
            for _ in range(max(1, attempts)):
                result = await _run_cloud_provider(pname, text, broadcast, brief)
                if result is not _QUOTA:
                    break
            if result is _QUOTA or result is None:
                continue  # provider exhausted/transient — try the next one
            return        # handled
        # every provider failed → graceful offline fallback
        await broadcast({"type": "auto_offline",
                         "reason": "All AI providers are rate-limited right now."})
        await _run_offline(text, broadcast)
    except Exception as exc:  # pragma: no cover - defensive
        await broadcast({"type": "error",
                         "content": f"FLORA hit an unexpected error: {exc}"})
    finally:
        await broadcast({"type": "typing", "active": False})
