"""Module 06 — Auth seed definitions (dynamic from glow-deploy.yaml).

Auth providers are driven by the auth.providers list in config.
IDs are deterministic via sid("auth/{name}").
"""

from database.seeds.config import get_auth_providers, load_deploy_config
from database.seeds.ids import sid

try:
    _config = load_deploy_config()
except FileNotFoundError:
    _config = {"auth": {"providers": []}}

_auth_providers = get_auth_providers(_config)

# Lookup: auth name → UUID
AUTH_IDS = {p["name"]: sid(f"auth/{p['name']}") for p in _auth_providers}


def _item_names_for_protocol(protocol: str) -> list[str]:
    if protocol == "google":
        return ["clientId", "clientSecret"]
    return ["clientId", "clientSecret", "discoveryUrl", "clientAuthMethod",
            "authorizationUrl", "tokenUrl"]


# auth_name → list of item UUIDs
AUTH_ITEM_IDS = {}
for _p in _auth_providers:
    _items = _item_names_for_protocol(_p.get("protocol", "oidc"))
    AUTH_ITEM_IDS[_p["name"]] = [sid(f"auth-item/{_p['name']}/{item}") for item in _items]

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
