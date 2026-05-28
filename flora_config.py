"""
FLORA Intelligence — configuration.

All API keys are loaded from the environment (or an optional .flora.env file
next to this module). Keys are NEVER hardcoded. If no provider keys are set,
FLORA still runs fully in offline mode.
"""
import os
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent

# ── Optional .flora.env loader (tiny KEY=VALUE parser — no external dep) ─────────
_ENV_FILE = BASE_DIR / ".flora.env"
if _ENV_FILE.exists():
    try:
        for _line in _ENV_FILE.read_text(encoding="utf-8").splitlines():
            _line = _line.strip()
            if not _line or _line.startswith("#") or "=" not in _line:
                continue
            _key, _, _val = _line.partition("=")
            _key = _key.strip()
            _val = _val.strip().strip('"').strip("'")
            if _key and _key not in os.environ:
                os.environ[_key] = _val
    except Exception as _e:  # pragma: no cover - defensive
        print(f"[FLORA] .flora.env parse warning: {_e}")

# ── API keys (environment only) ─────────────────────────────────────────────────
GROQ_API_KEY     = os.getenv("GROQ_API_KEY", "").strip()
CEREBRAS_API_KEY = os.getenv("CEREBRAS_API_KEY", "").strip()
MISTRAL_API_KEY  = os.getenv("MISTRAL_API_KEY", "").strip()
GEMINI_API_KEY   = os.getenv("GEMINI_API_KEY", "").strip()
GEMINI_API_KEY2  = os.getenv("GEMINI_API_KEY2", "").strip()


def _gemini_key_pool():
    """Pool every configured Gemini key, de-duplicated, order preserved.

    Extra free-tier keys may be supplied as a comma-separated GEMINI_API_KEYS
    list. Pooling and round-robining them stretches free quota across far
    longer chat sessions.
    """
    raw = [GEMINI_API_KEY, GEMINI_API_KEY2]
    raw += [k.strip() for k in os.getenv("GEMINI_API_KEYS", "").split(",")]
    seen, pool = set(), []
    for k in raw:
        if k and k not in seen:
            seen.add(k)
            pool.append(k)
    return pool


GEMINI_API_KEYS = _gemini_key_pool()

# ── Provider definitions ────────────────────────────────────────────────────────
# Every provider below exposes an OpenAI-compatible /chat/completions endpoint,
# so a single `openai` client handles all of them by swapping base_url + key.
PROVIDERS = {
    "groq": {
        "label": "Groq",
        "base_url": "https://api.groq.com/openai/v1",
        # gpt-oss-120b uses native structured tool calling — it avoids the
        # malformed "<function=name{...}" syntax that llama-3.3-70b emits on Groq.
        "model": "openai/gpt-oss-120b",
        "keys": [GROQ_API_KEY],
        "max_history": 8,
    },
    "cerebras": {
        "label": "Cerebras",
        "base_url": "https://api.cerebras.ai/v1",
        "model": "llama-3.3-70b",
        "keys": [CEREBRAS_API_KEY],
        "max_history": 8,
    },
    "mistral": {
        "label": "Mistral",
        "base_url": "https://api.mistral.ai/v1",
        "model": "mistral-small-latest",
        "keys": [MISTRAL_API_KEY],
        "max_history": 8,
    },
    "gemini": {
        "label": "Gemini",
        "base_url": "https://generativelanguage.googleapis.com/v1beta/openai/",
        "model": "gemini-2.0-flash",
        "keys": GEMINI_API_KEYS,
        "max_history": 12,
    },
}

# Preferred fallback order. Only providers with at least one key are used.
PROVIDER_ORDER = ["groq", "cerebras", "mistral", "gemini"]


def active_providers():
    """Ordered provider names that have at least one non-empty API key."""
    return [
        name for name in PROVIDER_ORDER
        if any(k for k in PROVIDERS.get(name, {}).get("keys", []))
    ]


def provider_keys(name):
    """Non-empty keys for a provider (supports round-robin across keys)."""
    return [k for k in PROVIDERS.get(name, {}).get("keys", []) if k]


# ── FLORA runtime settings ──────────────────────────────────────────────────────
FLORA_MAX_HISTORY   = 20                                  # chat turns kept on disk
FLORA_MAX_ROUNDS    = 8                                   # agentic tool rounds / request
REQUEST_TIMEOUT_S   = 60                                  # per provider HTTP call
FLORA_HISTORY_FILE  = BASE_DIR / ".flora_chat_history.json"
FLORA_SCHEDULE_FILE = BASE_DIR / ".flora_schedule.json"
