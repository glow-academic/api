"""Auth config item seed definitions.

Defines the configuration fields for each authentication provider.
Encrypted items (clientId, clientSecret) have their values stored
in keys_resource via auth_item_keys_resource.
Non-encrypted items (tenantId, discoveryUrl, etc.) have their values
stored in auth_item_values_resource.
"""

from uuid import UUID

# ---------------------------------------------------------------------------
# Google items
# ---------------------------------------------------------------------------

GOOGLE_CLIENT_SECRET_ITEM = UUID("019b3be4-3119-7fae-9dea-08a64aff6240")
GOOGLE_CLIENT_ID_ITEM = UUID("019b3be4-3119-7fdf-908e-6a6b9430f085")

GOOGLE_ITEM_IDS = [GOOGLE_CLIENT_SECRET_ITEM, GOOGLE_CLIENT_ID_ITEM]

# ---------------------------------------------------------------------------
# Microsoft items
# ---------------------------------------------------------------------------

MS_CLIENT_SECRET_ITEM = UUID("019b3be4-3119-7feb-9764-0741b7080380")
MS_CLIENT_ID_ITEM = UUID("019b3be4-3119-7fed-b752-bf6209d31c1d")
MS_TENANT_ID_ITEM = UUID("019b3be4-3119-7ff4-a277-aa213eac5632")
MS_USER_INFO_URL_ITEM = UUID("019b3be4-3119-7ff8-9a20-27a9c8e586d5")
MS_DISCOVERY_URL_ITEM = UUID("019b3be4-311a-7004-bc8a-cd80f62b310e")
MS_CLIENT_AUTH_METHOD_ITEM = UUID("019b3be4-311a-7008-8bba-868f8b70fe13")
MS_AUTH_URL_ITEM = UUID("019b3be4-311a-700d-8fc0-9ba72a9bd318")
MS_TOKEN_URL_ITEM = UUID("019b3be4-311a-7014-96a8-573949e45256")

MICROSOFT_ITEM_IDS = [
    MS_CLIENT_SECRET_ITEM,
    MS_CLIENT_ID_ITEM,
    MS_TENANT_ID_ITEM,
    MS_USER_INFO_URL_ITEM,
    MS_DISCOVERY_URL_ITEM,
    MS_CLIENT_AUTH_METHOD_ITEM,
    MS_AUTH_URL_ITEM,
    MS_TOKEN_URL_ITEM,
]

# ---------------------------------------------------------------------------
# Item definitions
# ---------------------------------------------------------------------------

items = [
    # Google
    dict(
        id=GOOGLE_CLIENT_SECRET_ITEM,
        name="clientSecret",
        description="Google Client Secret",
        encrypted=True,
        position=1,
    ),
    dict(
        id=GOOGLE_CLIENT_ID_ITEM,
        name="clientId",
        description="Google Client ID",
        encrypted=True,
        position=2,
    ),
    # Microsoft
    dict(
        id=MS_CLIENT_SECRET_ITEM,
        name="clientSecret",
        description="Microsoft Entra ID Client Secret",
        encrypted=True,
        position=1,
    ),
    dict(
        id=MS_CLIENT_ID_ITEM,
        name="clientId",
        description="Microsoft Entra ID Client ID",
        encrypted=True,
        position=2,
    ),
    dict(
        id=MS_TENANT_ID_ITEM,
        name="tenantId",
        description="Microsoft Tenant ID",
        encrypted=False,
        position=3,
    ),
    dict(
        id=MS_USER_INFO_URL_ITEM,
        name="userInfoUrl",
        description="Microsoft UserInfo Endpoint",
        encrypted=False,
        position=4,
    ),
    dict(
        id=MS_DISCOVERY_URL_ITEM,
        name="discoveryUrl",
        description="Microsoft Discovery URL",
        encrypted=False,
        position=5,
    ),
    dict(
        id=MS_CLIENT_AUTH_METHOD_ITEM,
        name="clientAuthMethod",
        description="Microsoft Client Auth Method",
        encrypted=False,
        position=6,
    ),
    dict(
        id=MS_AUTH_URL_ITEM,
        name="authorizationUrl",
        description="Microsoft Authorization Endpoint",
        encrypted=False,
        position=7,
    ),
    dict(
        id=MS_TOKEN_URL_ITEM,
        name="tokenUrl",
        description="Microsoft Token Endpoint",
        encrypted=False,
        position=8,
    ),
]
