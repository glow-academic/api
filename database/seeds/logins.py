"""Login seed definitions — builds logins_resource entries from auth + profile configs.

Each auth provider gets a login_type="auth" entry with auth_id pointing to
the auth resource. Each profile linked to settings gets a login_type="profile"
entry with profile_id pointing to the profile resource.

IDs are deterministic via sid("login/auth/{slug}") and sid("login/profile/{slug}").
"""

from __future__ import annotations

from uuid import UUID

from database.seeds.auths import AUTH_RESOURCE_IDS
from database.seeds.config import get_auth_providers, load_deploy_config
from database.seeds.ids import sid

try:
    _config = load_deploy_config()
except FileNotFoundError:
    _config = {"auth": {"providers": []}}

_auth_providers = get_auth_providers(_config)

# ---------------------------------------------------------------------------
# Icon mapping — provider name → icon slug for auth logins
# ---------------------------------------------------------------------------

_AUTH_ICON_MAP: dict[str, str] = {
    "google": "globe",
    "microsoft": "grid",
    "learnloop": "sparkles",
}

_DEFAULT_AUTH_ICON_SLUG = "key"


# ---------------------------------------------------------------------------
# Auth-based logins — one per auth provider
# ---------------------------------------------------------------------------

def build_auth_logins(auth_providers: list[dict]) -> list[dict]:
    """Build logins_resource entries from auth provider configs."""
    logins: list[dict] = []
    for p in auth_providers:
        name = p.get("display_name", p["name"])
        slug = p.get("slug", p["name"])
        auth_resource_id = AUTH_RESOURCE_IDS.get(p["name"])
        if not auth_resource_id:
            continue
        icon_slug = _AUTH_ICON_MAP.get(p["name"].lower(), _DEFAULT_AUTH_ICON_SLUG)
        logins.append(dict(
            id=sid(f"login/auth/{slug}"),
            auth_id=auth_resource_id,
            profile_id=None,
            icon_id=sid(f"icon/{icon_slug}"),
            login_type="auth",
            display_name=f"Continue with {name}",
        ))
    return logins


# ---------------------------------------------------------------------------
# Profile-based logins — one per profile resource
# ---------------------------------------------------------------------------

def build_profile_logins(profile_entries: list[dict]) -> list[dict]:
    """Build logins_resource entries from profile definitions.

    Each entry should have:
      - "name": display name of the profile
      - "resource_id": UUID of the profiles_resource entry
    """
    logins: list[dict] = []
    for p in profile_entries:
        name = p["name"]
        resource_id = p["resource_id"]
        slug = name.lower().replace(" ", "-")
        logins.append(dict(
            id=sid(f"login/profile/{slug}"),
            auth_id=None,
            profile_id=resource_id,
            icon_id=sid("icon/user"),
            login_type="profile",
            display_name=f"Continue as {name}",
        ))
    return logins


# ---------------------------------------------------------------------------
# Default auth logins (derived from glow-deploy.yaml at import time)
# ---------------------------------------------------------------------------

AUTH_LOGINS = build_auth_logins(_auth_providers)
AUTH_LOGIN_IDS: list[UUID] = [lg["id"] for lg in AUTH_LOGINS]
