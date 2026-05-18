"""Dynamic key seeding — reads all credentials from glow-deploy.yaml.

Creates key_resources, provider_keys, auth_item_keys, and auth_item_values
for every provider in the config. Derives fields from config — no hardcoded lists.
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

# Metadata fields — not auth config items
_SKIP_FIELDS = {"name", "protocol", "slug", "display_name", "id"}
# Encrypted fields
_ENCRYPTED_FIELDS = {"client_id", "client_secret"}
# Config field → camelCase item name
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

# --- Key resources (created directly, not updated) ---
key_resources = []

# --- AI provider keys ---
provider_keys = []

for p in get_ai_providers(_config):
    raw_key = p.get("key", "")
    encrypted = encrypt_api_key(raw_key) if raw_key else ""
    key_id = sid(f"key/ai/{p['name']}")
    provider_id = PROVIDER_IDS.get(p["name"])
    if not provider_id:
        continue

    # Create the key resource
    key_resources.append(dict(
        id=key_id,
        name=f"{p['name'].upper()}_API_KEY",
        description=f"{p['name']} API Key",
        key=encrypted,
    ))

    # Link provider → key (only if key has a value)
    if raw_key:
        provider_keys.append(dict(
            id=sid(f"provider-key/{p['name']}"),
            provider_id=provider_id,
            key_id=key_id,
            key=encrypted,
            name=f"{p['name'].upper()}_API_KEY",
            description=f"{p['name']} API Key",
        ))

# --- Auth provider keys + items ---
auth_item_keys = []
auth_item_values = []

for ap in get_auth_providers(_config):
    auth_id = AUTH_IDS.get(ap["name"])
    if not auth_id:
        continue

    for field_name, field_value in ap.items():
        if field_name in _SKIP_FIELDS:
            continue

        item_name = _FIELD_TO_ITEM.get(field_name, field_name)

        if field_name in _ENCRYPTED_FIELDS:
            # Create key resource for this credential
            key_id = sid(f"key/auth/{ap['name']}/{field_name}")
            encrypted_value = encrypt_api_key(field_value) if field_value else ""
            key_resources.append(dict(
                id=key_id,
                name=f"{ap.get('display_name', ap['name'])} {item_name}",
                description="",
                key=encrypted_value,
            ))

            # Link auth_item → key (only if value exists)
            if field_value:
                item_id = sid(f"auth-item/{ap['name']}/{item_name}")
                auth_item_keys.append(dict(
                    id=sid(f"auth-item-key/{ap['name']}/{field_name}"),
                    auth_id=auth_id,
                    item_id=item_id,
                    key_id=key_id,
                ))
        else:
            # Plaintext config value
            if not field_value:
                continue
            auth_item_values.append(dict(
                id=sid(f"auth-item-value/{ap['name']}/{item_name}"),
                auth_id=auth_id,
                item_id=sid(f"auth-item/{ap['name']}/{item_name}"),
                value=field_value,
            ))

# No more key_resource_updates — keys are created directly
key_resource_updates = []

# Exports for settings linkage
PROVIDER_KEY_IDS = [pk["id"] for pk in provider_keys]
AUTH_ITEM_KEY_IDS = [aik["id"] for aik in auth_item_keys]
AUTH_ITEM_VALUE_IDS = [aiv["id"] for aiv in auth_item_values]
AUTH_ID_LIST = list(AUTH_IDS.values())

# Auth resource IDs for settings linkage (junctions need resource IDs, not artifact IDs)
from database.seeds.auths import AUTH_RESOURCE_IDS  # noqa: E402
AUTH_RESOURCE_ID_LIST = list(AUTH_RESOURCE_IDS.values())
