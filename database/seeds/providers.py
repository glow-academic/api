"""Module 02 — Provider seed definitions (dynamic from glow-deploy.yaml).

Providers are driven by the ai.providers list in glow-deploy.yaml.
IDs are deterministic via sid("provider/{name}").
"""

from uuid import UUID

from database.seeds.config import get_ai_providers, load_deploy_config
from database.seeds.ids import sid

try:
    _config = load_deploy_config()
except FileNotFoundError:
    _config = {"ai": {"providers": []}}

_ai_providers = get_ai_providers(_config)

# Lookup: provider name → resource UUID (used by models, keys)
PROVIDER_IDS = {p["name"]: sid(f"provider-resource/{p['name']}") for p in _ai_providers}

providers = [
    dict(
        id=sid(f"provider/{p['name']}"),
        resource_id=sid(f"provider-resource/{p['name']}"),
        name=p["name"],
        description=f'{p["name"]} AI provider',
        active_flag=True,
        endpoint=p.get("endpoint"),
        key=p.get("key"),
    )
    for p in _ai_providers
]
