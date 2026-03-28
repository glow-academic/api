"""Module 02 — Provider seed definitions.

Each dict maps directly to CreateProviderItem fields.
String fields (name, description, active_flag) are resolved by the _impl function.

If AI_PROVIDER=learnloop, sets endpoint to the LearnLoop AI Gateway URL
so Glow routes all model calls through LearnLoop's proxy.
"""

from uuid import UUID

from database.seeds.config import get_ai_config, load_deploy_config

# ---------------------------------------------------------------------------
# Deterministic IDs — importable by models
# ---------------------------------------------------------------------------

OPENAI = UUID("019bb2af-b2a3-7466-ad52-1a8593d00b6f")
GEMINI = UUID("019bb2af-b2a5-7219-9e1d-2439eee0b618")

# ---------------------------------------------------------------------------
# Load config for endpoint
# ---------------------------------------------------------------------------

try:
    _config = load_deploy_config()
except FileNotFoundError:
    _config = {"ai": {"provider": "direct"}}

_ai = get_ai_config(_config)

# ---------------------------------------------------------------------------
# Provider definitions
# ---------------------------------------------------------------------------

providers = [
    dict(
        id=OPENAI,
        name="openai",
        description="Provider description",
        active_flag=True,
        endpoint=_ai.get("openai_endpoint"),
    ),
    dict(
        id=GEMINI,
        name="gemini",
        description="Provider description",
        active_flag=True,
        endpoint=_ai.get("gemini_endpoint"),
    ),
]
