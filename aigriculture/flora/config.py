"""FLORA configuration — API keys come from the environment only.

Every provider exposes an OpenAI-compatible endpoint, so one client handles all
of them by swapping base_url + key. With no keys set, FLORA runs fully offline.
Keys are read live (not at import) so a .env loaded at startup is always seen.
"""

from __future__ import annotations

import os
from typing import List

PROVIDERS = {
    "groq": {
        "label": "Groq",
        "base_url": "https://api.groq.com/openai/v1",
        "model": "openai/gpt-oss-120b",
        "env": ["GROQ_API_KEY"],
        "max_history": 8,
    },
    "cerebras": {
        "label": "Cerebras",
        "base_url": "https://api.cerebras.ai/v1",
        "model": "llama-3.3-70b",
        "env": ["CEREBRAS_API_KEY"],
        "max_history": 8,
    },
    "mistral": {
        "label": "Mistral",
        "base_url": "https://api.mistral.ai/v1",
        "model": "mistral-small-latest",
        "env": ["MISTRAL_API_KEY"],
        "max_history": 8,
    },
    "gemini": {
        "label": "Gemini",
        "base_url": "https://generativelanguage.googleapis.com/v1beta/openai/",
        "model": "gemini-2.0-flash",
        "env": ["GEMINI_API_KEY", "GEMINI_API_KEYS"],
        "max_history": 12,
    },
}
PROVIDER_ORDER = ["groq", "cerebras", "mistral", "gemini"]

FLORA_MAX_HISTORY = 20
FLORA_MAX_ROUNDS = 8
REQUEST_TIMEOUT_S = 60


def provider_keys(name: str) -> List[str]:
    """Live, de-duplicated, non-empty keys for a provider (supports round-robin)."""
    keys, seen = [], set()
    for var in PROVIDERS.get(name, {}).get("env", []):
        for raw in os.getenv(var, "").split(","):
            k = raw.strip()
            if k and k not in seen:
                seen.add(k)
                keys.append(k)
    return keys


def active_providers() -> List[str]:
    """Ordered provider names that currently have at least one key set."""
    return [name for name in PROVIDER_ORDER if provider_keys(name)]
