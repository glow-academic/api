"""LearnLoop integration module — optional, included when AUTH_PROVIDER=learnloop.

Provides:
  - LearnLoop auth entry (OIDC provider for "Login with LearnLoop")
  - Encrypted key values (client_id, client_secret)
  - Auth item keys + values (OIDC config: discoveryUrl, clientAuthMethod)
  - Auth IDs for linking to settings

Reads credentials from glow-deploy.yaml via get_auth_config().
"""

from app.utils.auth.encrypt_api_key import encrypt_api_key

from database.seeds.auths import LEARNLOOP_AUTH
from database.seeds.config import get_auth_config, load_deploy_config
from database.seeds.ids import sid
from database.seeds.resources.items import (
    LL_AUTH_URL_ITEM,
    LL_CLIENT_AUTH_METHOD_ITEM,
    LL_CLIENT_ID_ITEM,
    LL_CLIENT_SECRET_ITEM,
    LL_DISCOVERY_URL_ITEM,
    LL_TOKEN_URL_ITEM,
)
from database.seeds.resources.keys import (
    LEARNLOOP_CLIENT_ID_KEY,
    LEARNLOOP_CLIENT_SECRET_KEY,
)

# ---------------------------------------------------------------------------
# Read config
# ---------------------------------------------------------------------------

try:
    _config = load_deploy_config()
    _auth = get_auth_config(_config)
except FileNotFoundError:
    _auth = {"provider": "keycloak"}

ENABLED = _auth.get("provider") == "learnloop"

# ---------------------------------------------------------------------------
# Encrypted key values (only when enabled)
# ---------------------------------------------------------------------------

if ENABLED:
    _ll_client_id = encrypt_api_key(_auth.get("client_id", ""))
    _ll_client_secret = encrypt_api_key(_auth.get("client_secret", ""))
    _ll_issuer = _auth.get("issuer", "https://api.learn-loop.org")
    _ll_issuer_internal = _auth.get("issuer_internal", _ll_issuer)
else:
    _ll_client_id = ""
    _ll_client_secret = ""
    _ll_issuer = ""
    _ll_issuer_internal = ""

# ---------------------------------------------------------------------------
# Deterministic IDs
# ---------------------------------------------------------------------------

AIK_LL_CLIENT_ID = sid("learnloop/auth-item-key/client-id")
AIK_LL_CLIENT_SECRET = sid("learnloop/auth-item-key/client-secret")
AIV_LL_DISCOVERY_URL = sid("learnloop/auth-item-value/discovery-url")
AIV_LL_CLIENT_AUTH_METHOD = sid("learnloop/auth-item-value/client-auth-method")
AIV_LL_AUTH_URL = sid("learnloop/auth-item-value/authorization-url")
AIV_LL_TOKEN_URL = sid("learnloop/auth-item-value/token-url")

# ---------------------------------------------------------------------------
# Key resource updates — populate base key resources with encrypted values
# ---------------------------------------------------------------------------

key_resource_updates = [
    dict(id=LEARNLOOP_CLIENT_ID_KEY, key=_ll_client_id),
    dict(id=LEARNLOOP_CLIENT_SECRET_KEY, key=_ll_client_secret),
] if ENABLED else []

# ---------------------------------------------------------------------------
# Auth item keys — link LearnLoop auth items to their encrypted keys
# ---------------------------------------------------------------------------

auth_item_keys = [
    dict(
        id=AIK_LL_CLIENT_ID,
        auth_id=LEARNLOOP_AUTH,
        item_id=LL_CLIENT_ID_ITEM,
        key_id=LEARNLOOP_CLIENT_ID_KEY,
    ),
    dict(
        id=AIK_LL_CLIENT_SECRET,
        auth_id=LEARNLOOP_AUTH,
        item_id=LL_CLIENT_SECRET_ITEM,
        key_id=LEARNLOOP_CLIENT_SECRET_KEY,
    ),
] if ENABLED else []

# ---------------------------------------------------------------------------
# Auth item values — non-encrypted OIDC config
# ---------------------------------------------------------------------------

auth_item_values = [
    dict(
        id=AIV_LL_DISCOVERY_URL,
        auth_id=LEARNLOOP_AUTH,
        item_id=LL_DISCOVERY_URL_ITEM,
        value=f"{_ll_issuer_internal}/.well-known/openid-configuration",
    ),
    dict(
        id=AIV_LL_CLIENT_AUTH_METHOD,
        auth_id=LEARNLOOP_AUTH,
        item_id=LL_CLIENT_AUTH_METHOD_ITEM,
        value="client_secret_post",
    ),
    dict(
        id=AIV_LL_AUTH_URL,
        auth_id=LEARNLOOP_AUTH,
        item_id=LL_AUTH_URL_ITEM,
        value=f"{_ll_issuer}/authorize",
    ),
    dict(
        id=AIV_LL_TOKEN_URL,
        auth_id=LEARNLOOP_AUTH,
        item_id=LL_TOKEN_URL_ITEM,
        value=f"{_ll_issuer_internal}/token",
    ),
] if ENABLED else []

# ---------------------------------------------------------------------------
# Exported IDs for settings linkage
# ---------------------------------------------------------------------------

AUTH_ITEM_KEY_IDS = [AIK_LL_CLIENT_ID, AIK_LL_CLIENT_SECRET] if ENABLED else []
AUTH_ITEM_VALUE_IDS = [AIV_LL_DISCOVERY_URL, AIV_LL_CLIENT_AUTH_METHOD, AIV_LL_AUTH_URL, AIV_LL_TOKEN_URL] if ENABLED else []
AUTH_IDS = [LEARNLOOP_AUTH] if ENABLED else []

# Required by _run_key_seeds (no provider keys for LearnLoop — it's an auth, not a provider)
provider_keys = []
