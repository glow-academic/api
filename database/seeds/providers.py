"""Module 02 — Provider seed definitions.

Each dict maps directly to CreateProviderItem fields.
String fields (name, description, active_flag) are resolved by the _impl function.
"""

from uuid import UUID

# ---------------------------------------------------------------------------
# Deterministic IDs — importable by models
# ---------------------------------------------------------------------------

OPENAI = UUID("019bb2af-b2a3-7466-ad52-1a8593d00b6f")
GEMINI = UUID("019bb2af-b2a5-7219-9e1d-2439eee0b618")

# ---------------------------------------------------------------------------
# Provider definitions
# ---------------------------------------------------------------------------

providers = [
    dict(
        id=OPENAI,
        name="openai",
        description="Provider description",
        active_flag=True,
    ),
    dict(
        id=GEMINI,
        name="gemini",
        description="Provider description",
        active_flag=True,
    ),
]
