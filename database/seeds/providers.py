"""Module 02 — Provider seed definitions (dynamic from glow-deploy.yaml).

Providers are driven by the ai.providers list in glow-deploy.yaml.
No hardcoded provider names — any provider can be added via config.
"""

from uuid import UUID

from database.seeds.config import get_ai_providers, load_deploy_config
from database.seeds.ids import sid

# Legacy UUIDs — existing deployments have rows with these IDs.
# New providers get deterministic IDs via sid().
_LEGACY_IDS = {
    "openai": UUID("019bb2af-b2a3-7466-ad52-1a8593d00b6f"),
    "gemini": UUID("019bb2af-b2a5-7219-9e1d-2439eee0b618"),
}

try:
    _config = load_deploy_config()
except FileNotFoundError:
    _config = {"ai": {"providers": []}}

_ai_providers = get_ai_providers(_config)


def _provider_id(name: str) -> UUID:
    return _LEGACY_IDS.get(name, sid(f"provider/{name}"))


# Lookup: provider name → UUID (used by models, keys)
PROVIDER_IDS = {p["name"]: _provider_id(p["name"]) for p in _ai_providers}

providers = [
    dict(
        id=_provider_id(p["name"]),
        name=p["name"],
        description=f'{p["name"]} AI provider',
        active_flag=True,
        endpoint=p.get("endpoint"),
    )
    for p in _ai_providers
]
