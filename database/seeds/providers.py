"""Module 02 — Provider seed definitions (dynamic from glow-deploy.yaml).

Providers are driven by the ai.providers list in glow-deploy.yaml.
IDs are deterministic via sid("provider/{name}").
Keys are encrypted with SECRET_KEY before storage.
"""

from database.seeds.config import get_ai_providers, load_deploy_config
from database.seeds.ids import sid

try:
    from app.utils.auth.encrypt_api_key import encrypt_api_key
except ImportError:
    def encrypt_api_key(key: str) -> str:
        return key  # fallback for testing

try:
    _config = load_deploy_config()
except FileNotFoundError:
    _config = {"ai": {"providers": []}}

_ai_providers = get_ai_providers(_config)

# Lookup: provider name → resource UUID (used by models, keys)
PROVIDER_IDS = {p["name"]: sid(f"provider-resource/{p['name']}") for p in _ai_providers}


def _encrypt_key(raw_key: str | None) -> str:
    """Encrypt a provider API key, or return empty string if none."""
    if not raw_key:
        return ""
    return encrypt_api_key(raw_key)


providers = [
    dict(
        id=sid(f"provider/{p['name']}"),
        resource_id=sid(f"provider-resource/{p['name']}"),
        name=p["name"],
        description=f'{p["name"]} AI provider',
        flag_ids=[sid("flag/provider-active")],
        endpoint=p.get("endpoint"),
        key=_encrypt_key(p.get("key")),
        value=p["name"],
    )
    for p in _ai_providers
]
