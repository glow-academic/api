"""Module 06 — Auth seed definitions (dynamic from glow-deploy.yaml).

Auth providers are driven by the auth.providers list in config.
No hardcoded provider names.
"""

from uuid import UUID
from database.seeds.config import get_auth_providers, load_deploy_config
from database.seeds.ids import sid

# Legacy UUIDs for existing deployments
_LEGACY_AUTH_IDS = {
    "google": UUID("019b3be4-3117-7aa4-aa34-0041aa51d1d8"),
    "microsoft": UUID("019b3be4-3117-7afc-8d1d-a2815d70f294"),
}

try:
    _config = load_deploy_config()
except FileNotFoundError:
    _config = {"auth": {"providers": []}}

_auth_providers = get_auth_providers(_config)


def _auth_id(name: str) -> UUID:
    return _LEGACY_AUTH_IDS.get(name, sid(f"auth/{name}"))


# Lookup: auth name -> UUID
AUTH_IDS = {p["name"]: _auth_id(p["name"]) for p in _auth_providers}

# Generate item IDs for each auth provider
def _item_names_for_protocol(protocol: str) -> list[str]:
    if protocol == "google":
        return ["clientId", "clientSecret"]
    # oidc and others need full config
    return ["clientId", "clientSecret", "discoveryUrl", "clientAuthMethod",
            "authorizationUrl", "tokenUrl"]

AUTH_ITEM_IDS = {}  # auth_name -> list of item UUIDs
for _p in _auth_providers:
    _items = _item_names_for_protocol(_p.get("protocol", "oidc"))
    AUTH_ITEM_IDS[_p["name"]] = [sid(f"auth-item/{_p['name']}/{item}") for item in _items]

auths = [
    dict(
        id=_auth_id(p["name"]),
        name=p.get("display_name", p["name"]),
        description=f'{p.get("display_name", p["name"])} authentication',
        slug=p.get("slug", p["name"]),
        protocol=p.get("protocol", "oidc"),
        active_flag=True,
        item_ids=AUTH_ITEM_IDS.get(p["name"], []),
    )
    for p in _auth_providers
]
