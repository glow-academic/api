"""Resource items — dynamically generated from glow-deploy.yaml.

Each auth provider's items are derived from its config fields.
Encrypted: client_id, client_secret (always present).
Plaintext: any other fields declared in the config (discovery_url,
authorization_url, token_url, tenant_id, user_info_url, etc.).

Adding a new auth provider (GitHub, Discord, etc.) only requires
adding its config to glow-deploy.local.yaml — no code changes.
"""

from database.seeds.config import get_auth_providers, load_deploy_config
from database.seeds.ids import sid

try:
    _config = load_deploy_config()
except FileNotFoundError:
    _config = {}

# Fields that are always encrypted auth_item_keys (not plaintext items)
_ENCRYPTED_FIELDS = {"client_id", "client_secret"}

# Fields that are metadata, not auth config items
_SKIP_FIELDS = {"name", "protocol", "slug", "display_name"}

# Map config field names to auth item names (camelCase for Keycloak compat)
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

items = []
for p in get_auth_providers(_config):
    pos = 0
    for field_name in p:
        if field_name in _SKIP_FIELDS:
            continue
        # Always create the item definition (schema), even if value is empty.
        # Empty encrypted fields get populated at deploy time via env vars.
        item_name = _FIELD_TO_ITEM.get(field_name, field_name)
        encrypted = field_name in _ENCRYPTED_FIELDS
        pos += 1

        items.append(dict(
            id=sid(f"auth-item/{p['name']}/{item_name}"),
            name=item_name,
            description=f"{p.get('display_name', p['name'])} {item_name}",
            encrypted=encrypted,
            position=pos,
        ))
