"""Dynamic key seeding — reads all credentials from glow-deploy.yaml.

Creates provider_keys (AI API keys) and auth_item_keys/values (OAuth credentials)
for every provider in the config. No hardcoded provider names.
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

    # Encrypted items: client_id, client_secret
    client_id_raw = ap.get("client_id", "")
    client_secret_raw = ap.get("client_secret", "")

    if client_id_raw:
        cid_key = sid(f"key/auth/{ap['name']}/client-id")
        cid_item = sid(f"auth-item/{ap['name']}/clientId")
        encrypted_cid = encrypt_api_key(client_id_raw)
        auth_item_keys.append(dict(
            id=sid(f"auth-item-key/{ap['name']}/client-id"),
            auth_id=auth_id,
            item_id=cid_item,
            key_id=cid_key,
        ))
        key_resource_updates.append(dict(id=cid_key, key=encrypted_cid))

    if client_secret_raw:
        csecret_key = sid(f"key/auth/{ap['name']}/client-secret")
        csecret_item = sid(f"auth-item/{ap['name']}/clientSecret")
        encrypted_csecret = encrypt_api_key(client_secret_raw)
        auth_item_keys.append(dict(
            id=sid(f"auth-item-key/{ap['name']}/client-secret"),
            auth_id=auth_id,
            item_id=csecret_item,
            key_id=csecret_key,
        ))
        key_resource_updates.append(dict(id=csecret_key, key=encrypted_csecret))

    # Plaintext OIDC config values
    oidc_fields = {
        "discoveryUrl": ap.get("discovery_url", ""),
        "clientAuthMethod": ap.get("client_auth_method", ""),
        "authorizationUrl": ap.get("authorization_url", ""),
        "tokenUrl": ap.get("token_url", ""),
        "tenantId": ap.get("tenant_id", ""),
        "userInfoUrl": ap.get("user_info_url", ""),
    }
    for field_name, field_value in oidc_fields.items():
        if not field_value:
            continue
        auth_item_values.append(dict(
            id=sid(f"auth-item-value/{ap['name']}/{field_name}"),
            auth_id=auth_id,
            item_id=sid(f"auth-item/{ap['name']}/{field_name}"),
            value=field_value,
        ))

# Exports for settings linkage
PROVIDER_KEY_IDS = [pk["id"] for pk in provider_keys]
AUTH_ITEM_KEY_IDS = [aik["id"] for aik in auth_item_keys]
AUTH_ITEM_VALUE_IDS = [aiv["id"] for aiv in auth_item_values]
AUTH_ID_LIST = list(AUTH_IDS.values())
