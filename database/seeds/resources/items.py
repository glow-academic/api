"""Resource items — dynamically generated from glow-deploy.yaml.

Each auth provider gets items based on its protocol:
- google: clientId, clientSecret (both encrypted)
- oidc: clientId, clientSecret (encrypted) + discoveryUrl, clientAuthMethod,
        authorizationUrl, tokenUrl (plaintext)
"""

from database.seeds.config import get_auth_providers, load_deploy_config
from database.seeds.ids import sid

try:
    _config = load_deploy_config()
except FileNotFoundError:
    _config = {}

_ENCRYPTED_ITEMS = {"clientId", "clientSecret"}

def _items_for_protocol(protocol: str) -> list[str]:
    if protocol == "google":
        return ["clientId", "clientSecret"]
    return ["clientId", "clientSecret", "discoveryUrl", "clientAuthMethod",
            "authorizationUrl", "tokenUrl"]

items = []
for p in get_auth_providers(_config):
    item_names = _items_for_protocol(p.get("protocol", "oidc"))
    for pos, item_name in enumerate(item_names, 1):
        items.append(dict(
            id=sid(f"auth-item/{p['name']}/{item_name}"),
            name=item_name,
            description=f"{p.get('display_name', p['name'])} {item_name}",
            encrypted=item_name in _ENCRYPTED_ITEMS,
            position=pos,
        ))
