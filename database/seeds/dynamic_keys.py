"""Dynamic key seeding — reads all credentials from glow-deploy.yaml.

Creates provider_keys (AI API keys) and auth_item_keys/values (OAuth credentials)
for every provider in the config. Derives fields from config — no hardcoded field lists.
"""

from database.seeds.config import get_ai_providers, get_auth_providers, load_deploy_config
from database.seeds.ids import sid
from database.seeds.providers import PROVIDER_IDS
from database.seeds.auths import AUTH_IDS

try:
    from app.utils.auth.encrypt_api_key import encrypt_api_key
except ImportError:
    def encrypt_api_key(key: str) -> str:
        return key  # fallback for testing

try:
    _config = load_deploy_config()
except FileNotFoundError:
    _config = {}

# Fields that are encrypted (stored as auth_item_keys, not auth_item_values)
_ENCRYPTED_FIELDS = {"client_id", "client_secret"}

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

# --- AI provider keys ---
provider_keys = []
key_resource_updates = []

for p in get_ai_providers(_config):
    raw_key = p.get("key", "")
    if not raw_key:
        continue
    encrypted = encrypt_api_key(raw_key)
    key_id = sid(f"key/ai/{p['name']}")
    provider_id = PROVIDER_IDS.get(p["name"])
    if not provider_id:
        continue
    provider_keys.append(dict(
        id=sid(f"provider-key/{p['name']}"),
        provider_id=provider_id,
        key_id=key_id,
        key=encrypted,
        name=f"{p['name'].upper()}_API_KEY",
        description=f"{p['name']} API Key",
    ))
    key_resource_updates.append(dict(id=key_id, key=encrypted))

# --- Auth provider keys + items ---
auth_item_keys = []
auth_item_values = []

for ap in get_auth_providers(_config):
    auth_id = AUTH_IDS.get(ap["name"])
    if not auth_id:
        continue

    for field_name, field_value in ap.items():
        if field_name in _SKIP_FIELDS or not field_value:
            continue

        item_name = _FIELD_TO_ITEM.get(field_name, field_name)

        if field_name in _ENCRYPTED_FIELDS:
            # Encrypted → auth_item_key + key_resource_update
            key_sid = sid(f"key/auth/{ap['name']}/{field_name}")
            item_sid = sid(f"auth-item/{ap['name']}/{item_name}")
            encrypted_value = encrypt_api_key(field_value)
            auth_item_keys.append(dict(
                id=sid(f"auth-item-key/{ap['name']}/{field_name}"),
                auth_id=auth_id,
                item_id=item_sid,
                key_id=key_sid,
            ))
            key_resource_updates.append(dict(id=key_sid, key=encrypted_value))
        else:
            # Plaintext → auth_item_value
            auth_item_values.append(dict(
                id=sid(f"auth-item-value/{ap['name']}/{item_name}"),
                auth_id=auth_id,
                item_id=sid(f"auth-item/{ap['name']}/{item_name}"),
                value=field_value,
            ))

# Exports for settings linkage
PROVIDER_KEY_IDS = [pk["id"] for pk in provider_keys]
AUTH_ITEM_KEY_IDS = [aik["id"] for aik in auth_item_keys]
AUTH_ITEM_VALUE_IDS = [aiv["id"] for aiv in auth_item_values]
AUTH_ID_LIST = list(AUTH_IDS.values())
