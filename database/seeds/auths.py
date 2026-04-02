"""Module 06 — Auth seed definitions (dynamic from glow-deploy.yaml).

Auth providers and their items are derived from config fields.
No protocol templates — items come from whatever the config declares.
IDs are deterministic via sid("auth/{name}").
"""

from database.seeds.config import get_auth_providers, load_deploy_config
from database.seeds.ids import sid

try:
    _config = load_deploy_config()
except FileNotFoundError:
    _config = {"auth": {"providers": []}}

_auth_providers = get_auth_providers(_config)

# Metadata fields — not auth config items
_SKIP_FIELDS = {"name", "protocol", "slug", "display_name"}

# Map config field names to auth item names (camelCase)
_FIELD_TO_ITEM = {
    "client_id": "clientId",
    "client_secret": "clientSecret",
    "discovery_url": "discoveryUrl",
    "authorization_url": "authorizationUrl",
    "token_url": "tokenUrl",
    "client_auth_method": "clientAuthMethod",
    "tenant_id": "tenantId",
    "user_info_url": "userInfoUrl",
}

# Lookup: auth name → UUID
AUTH_IDS = {p["name"]: sid(f"auth/{p['name']}") for p in _auth_providers}

# auth_name → list of item UUIDs (derived from config fields)
AUTH_ITEM_IDS = {}
for _p in _auth_providers:
    _item_ids = []
    for _field in _p:
        if _field in _SKIP_FIELDS:
            continue
        _item_name = _FIELD_TO_ITEM.get(_field, _field)
        _item_ids.append(sid(f"auth-item/{_p['name']}/{_item_name}"))
    AUTH_ITEM_IDS[_p["name"]] = _item_ids

auths = [
    dict(
        id=sid(f"auth/{p['name']}"),
        name=p.get("display_name", p["name"]),
        description=f'{p.get("display_name", p["name"])} authentication',
        slug=p.get("slug", p["name"]),
        protocol=p.get("protocol", "oidc"),
        active_flag=True,
        item_ids=AUTH_ITEM_IDS.get(p["name"], []),
    )
    for p in _auth_providers
]
