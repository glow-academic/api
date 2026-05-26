"""Default IdP business logic — authorization, token exchange, code store.

Glow API acts as a standard OIDC provider. Clients (NextAuth, CLI, etc.)
see Glow as the identity provider. Internally, Glow delegates authentication
to Keycloak, which brokers to Google, Microsoft, or Glow's own profile-based
default-idp.

Two authorization flows:
  1. Browser OIDC (no profile_id): save session → redirect to Keycloak → callback → issue code
  2. Profile login (with profile_id): Keycloak broker calls /authorize → issue code directly
"""

import json
import os
import secrets
import time
from datetime import UTC, datetime
from typing import Any
from urllib.parse import urlencode
from uuid import UUID

from jose import jwt

from app.infra.globals import get_redis_client
from app.infra.identity.jwks import get_key_id, get_private_key
from app.infra.identity.keycloak_sync import get_idp_public_url
from app.infra.profile_identity_context import resolve_profile_identity_context
from app.tools.entries.emulations.search import search_emulations
from app.tools.entries.grant_consumptions.create import create_grant_consumption
from app.tools.entries.grant_consumptions.search import search_grant_consumptions
from app.tools.entries.grants.get import get_grants

# OIDC state storage — Redis-backed so auth codes / pending sessions / KC id
# tokens survive container restarts and blue/green switches. Previously these
# were in-memory dicts which dropped all flows in-flight on redeploy (users
# saw "Unexpected error when authenticating with identity provider").
_CODE_TTL = 600  # 10 minutes (authorization codes)
_SESSION_TTL = 600  # 10 minutes (pending browser sessions)
_KC_TOKEN_TTL = 86400  # 24 hours (KC id_token for federated logout)


async def _redis_set(key: str, value: Any, ttl: int) -> None:
    r = get_redis_client()
    if r is None:
        raise RuntimeError(
            "Redis client not initialized — required for OIDC state storage. "
            "Ensure REDIS_URL is set and the container can reach Redis."
        )
    await r.set(key, json.dumps(value), ex=ttl)


async def _redis_pop(key: str) -> Any | None:
    """Atomic get-and-delete. Returns None if key is missing (or expired)."""
    r = get_redis_client()
    if r is None:
        return None
    async with r.pipeline() as pipe:
        pipe.get(key)
        pipe.delete(key)
        value, _ = await pipe.execute()
    if value is None:
        return None
    return json.loads(value)


async def get_kc_id_token_for_logout(glow_id_token_hint: str | None) -> str | None:
    """Look up the KC id_token for a Glow-issued id_token.

    Decodes the Glow id_token to get the sub claim, then looks up the
    stored KC id_token. Returns None if not found (user will get a
    logout confirmation page instead of silent logout).
    """
    if not glow_id_token_hint:
        return None
    try:
        claims = jwt.decode(
            glow_id_token_hint,
            key="",
            options={"verify_signature": False, "verify_aud": False},
        )
        kc_sub = claims.get("sub", "")
        if not kc_sub:
            return None
        return await _redis_pop(f"oidc:kc_id_token:{kc_sub}")
    except Exception:
        return None


def _get_glow_base_url() -> str:
    """Get Glow API's public base URL (the OIDC issuer)."""
    return get_idp_public_url()


def _get_keycloak_base_url() -> str:
    """Get Keycloak's base URL for browser redirects."""
    origin = os.getenv("ORIGIN", "http://localhost")
    app_prefix = os.getenv("APP_PREFIX", "")
    realm = os.getenv("KEYCLOAK_REALM", "master")
    # Bare-localhost escape hatch is only for `make run` where keycloak
    # is reachable on its own port. Inside a docker compose deploy
    # (DOCKER_ENV=1), keycloak is fronted by nginx on the public ORIGIN.
    is_bare_local_dev = (
        "localhost" in origin.lower()
        and os.getenv("DOCKER_ENV") != "1"
    )
    if is_bare_local_dev:
        kc_base = os.getenv("KEYCLOAK_URL", "http://localhost:8080")
        return f"{kc_base}/auth/realms/{realm}"
    else:
        kc_base = f"{origin}{app_prefix}/auth"
        return f"{kc_base}/realms/{realm}"


def _get_keycloak_internal_url() -> str:
    """Get Keycloak's internal URL for server-to-server token exchange."""
    internal = os.getenv("KEYCLOAK_INTERNAL_URL", "")
    if internal:
        realm = os.getenv("KEYCLOAK_REALM", "master")
        app_prefix = os.getenv("APP_PREFIX", "")
        # nginx routes /auth/ to Keycloak — include it for internal access
        return f"{internal}/auth/realms/{realm}"
    return _get_keycloak_base_url()


def _get_glow_client_id() -> str:
    """Get the Keycloak client_id for Glow."""
    return os.getenv("AUTH_KEYCLOAK_ID", "glow-client")


def _get_glow_client_secret() -> str:
    """Get the Keycloak client_secret for Glow."""
    return os.getenv("AUTH_CLIENT_SECRET", "")


def get_idp_base_url() -> str:
    """Get the base URL for the IdP (public URL for issuer)."""
    return _get_glow_base_url()


def get_openid_configuration() -> dict[str, Any]:
    """Build the OIDC discovery document.

    Points to Glow API as the OIDC provider. Clients use these endpoints
    directly — they never see Keycloak.
    """
    base = _get_glow_base_url()

    return {
        "issuer": base,
        "authorization_endpoint": f"{base}/authorize",
        "token_endpoint": f"{base}/token",
        "jwks_uri": f"{base}/jwks",
        "userinfo_endpoint": f"{base}/userinfo",
        "end_session_endpoint": f"{base}/logout",
        "response_types_supported": ["code"],
        "grant_types_supported": ["authorization_code"],
        "subject_types_supported": ["public"],
        "id_token_signing_alg_values_supported": ["RS256"],
        "scopes_supported": ["openid", "profile", "email"],
        "token_endpoint_auth_methods_supported": [
            "client_secret_basic",
            "client_secret_post",
        ],
        "claims_supported": [
            "sub",
            "iss",
            "aud",
            "exp",
            "iat",
            "email",
            "name",
            "given_name",
            "family_name",
            "preferred_username",
            "profile_id",
            "role",
        ],
    }


class AuthorizationError(Exception):
    """Raised when authorization fails with a specific HTTP status."""

    def __init__(self, status_code: int, detail: str) -> None:
        self.status_code = status_code
        self.detail = detail
        super().__init__(detail)


# ── Flow 1: Browser OIDC (no profile_id) ────────────────────────────────


async def create_browser_session(
    *,
    redirect_uri: str,
    state: str | None,
    nonce: str | None,
    client_id: str,
    profile_id: str | None = None,
) -> str:
    """Save a pending browser session and return the Keycloak redirect URL.

    If profile_id is provided, adds kc_idp_hint to skip Keycloak's login page
    and go directly to that profile's default-idp.
    """
    internal_state = secrets.token_urlsafe(32)
    await _redis_set(
        f"oidc:session:{internal_state}",
        {
            "redirect_uri": redirect_uri,
            "state": state,
            "nonce": nonce,
            "client_id": client_id,
        },
        _SESSION_TTL,
    )

    kc_base = _get_keycloak_base_url()
    glow_base = _get_glow_base_url()
    callback_uri = f"{glow_base}/oidc-callback"

    params = {
        "response_type": "code",
        "client_id": _get_glow_client_id(),
        "redirect_uri": callback_uri,
        "scope": "openid profile email",
        "state": internal_state,
    }

    if profile_id:
        params["kc_idp_hint"] = f"default-idp-profile-{profile_id}"

    return f"{kc_base}/protocol/openid-connect/auth?{urlencode(params)}"


async def handle_oidc_callback(
    *,
    code: str,
    state: str,
) -> str:
    """Handle Keycloak's callback: exchange code, create Glow auth code, return redirect URL."""
    import httpx

    session = await _redis_pop(f"oidc:session:{state}")
    if not session:
        raise AuthorizationError(400, "Invalid or expired session")

    # Exchange Keycloak's code for tokens (server-to-server)
    kc_internal = _get_keycloak_internal_url()
    glow_base = _get_glow_base_url()
    callback_uri = f"{glow_base}/oidc-callback"

    async with httpx.AsyncClient(timeout=15.0) as http:
        resp = await http.post(
            f"{kc_internal}/protocol/openid-connect/token",
            data={
                "grant_type": "authorization_code",
                "client_id": _get_glow_client_id(),
                "client_secret": _get_glow_client_secret(),
                "code": code,
                "redirect_uri": callback_uri,
            },
        )

    if resp.status_code != 200:
        raise AuthorizationError(400, "Token exchange with identity provider failed")

    # Decode Keycloak's token to get user claims (trusted — direct from Keycloak)
    kc_tokens = resp.json()
    claims = jwt.decode(
        kc_tokens.get("access_token", kc_tokens.get("id_token", "")),
        key="",
        options={"verify_signature": False, "verify_aud": False},
    )

    # Store KC's id_token for federated logout (keyed by KC sub)
    kc_id_token = kc_tokens.get("id_token")
    if kc_id_token and claims.get("sub"):
        await _redis_set(f"oidc:kc_id_token:{claims['sub']}", kc_id_token, _KC_TOKEN_TTL)

    # Create a Glow-issued authorization code
    glow_code = secrets.token_urlsafe(32)
    await _redis_set(
        f"oidc:authz:{glow_code}",
        {
            "profile_id": claims.get("profile_id"),
            "email": claims.get("email", ""),
            "name": claims.get("name", claims.get("preferred_username", "")),
            "role": claims.get("role"),
            "nonce": session.get("nonce"),
            "client_id": session["client_id"],
            "redirect_uri": session["redirect_uri"],
            "is_emulation": claims.get("is_emulation", False),
            "actor_profile_id": claims.get("actor_profile_id"),
            "identity_provider": claims.get("identity_provider"),
            "sub": claims.get("sub", ""),
            "flow": "browser",
        },
        _CODE_TTL,
    )

    # Redirect back to the client's original callback
    redirect_params = {"code": glow_code}
    if session.get("state"):
        redirect_params["state"] = session["state"]

    return f"{session['redirect_uri']}?{urlencode(redirect_params)}"


# ── Flow 2: Profile login (Keycloak broker callback) ────────────────────


async def resolve_authorization(
    pool: Any,
    redis: Any,
    *,
    response_type: str,
    client_id: str,
    redirect_uri: str,
    state: str,
    nonce: str | None,
    profile_id: UUID | None,
    emulation_grant: UUID | None,
    login_hint: str | None,
) -> str:
    """Resolve authorization request → redirect URL with code.

    This handles the profile-based login flow where Keycloak's broker
    calls back to Glow's /authorize with a profile_id.

    Returns the full redirect URL string.
    Raises AuthorizationError on validation failures.
    """
    if response_type != "code":
        raise AuthorizationError(
            400,
            f"Unsupported response_type: {response_type}. Only 'code' is supported.",
        )

    if not nonce:
        nonce = secrets.token_urlsafe(32)

    resolved_profile_id = profile_id
    if emulation_grant is None and login_hint:
        try:
            emulation_grant = UUID(login_hint)
        except ValueError:
            raise AuthorizationError(400, "Invalid emulation grant token.")

    actor_profile_id: UUID | None = None

    if emulation_grant is not None:
        async with pool.acquire() as conn:
            grants = await get_grants(conn, [emulation_grant], redis)
            if not grants:
                raise AuthorizationError(404, "Emulation grant not found.")

            grant = grants[0]
            if grant.expires_at <= datetime.now(UTC):
                raise AuthorizationError(403, "Grant expired.")

            consumptions = await search_grant_consumptions(
                conn, redis, grant_ids=[emulation_grant], limit=1
            )
            if consumptions:
                raise AuthorizationError(403, "Grant already used.")

            await create_grant_consumption(conn, redis, grant_id=emulation_grant)
            actor_profile_id = grant.profiles_id

            emulations = await search_emulations(
                conn, redis, grant_ids=[emulation_grant], limit=1
            )
            if emulations:
                resolved_profile_id = emulations[0].profile_id

    if resolved_profile_id is None:
        raise AuthorizationError(400, "Missing profile_id for default IdP login.")

    profile = await resolve_profile_identity_context(
        pool,
        resolved_profile_id,
        redis,
        bypass_cache=True,
    )
    if profile is None:
        raise AuthorizationError(
            404, "Profile not found for this default IdP login."
        )
    resolved_email = profile.primary_email
    if resolved_email is None and profile.emails:
        resolved_email = profile.emails[0]

    if not resolved_email:
        raise AuthorizationError(
            404, "Profile or email not found for this default IdP login."
        )

    code = secrets.token_urlsafe(32)
    is_emulation = emulation_grant is not None
    await _redis_set(
        f"oidc:authz:{code}",
        {
            "profile_id": str(resolved_profile_id),
            "email": resolved_email,
            "name": profile.name or "",
            "role": None,  # role column dropped from profiles_resource
            "nonce": nonce,
            "client_id": client_id,
            "redirect_uri": redirect_uri,
            "is_emulation": is_emulation,
            "actor_profile_id": str(actor_profile_id) if actor_profile_id else None,
        },
        _CODE_TTL,
    )
    # No garbage collection needed — Redis enforces TTL per-key.

    return f"{redirect_uri}?code={code}&state={state}"


# ── Token exchange (both flows) ──────────────────────────────────────────


async def exchange_code_for_tokens(
    *,
    grant_type: str,
    code: str,
    redirect_uri: str,
    client_id: str,
    client_secret: str | None = None,
) -> dict[str, Any]:
    """Exchange authorization code for access + id tokens.

    Works for both browser OIDC flow and profile login flow.
    Returns the token response dict.
    Raises AuthorizationError on validation failures.
    """
    if grant_type != "authorization_code":
        raise AuthorizationError(
            400,
            f"Unsupported grant_type: {grant_type}. Only 'authorization_code' is supported.",
        )

    # Validate client_secret
    expected_secret = os.getenv("AUTH_CLIENT_SECRET", "")
    if not expected_secret:
        raise AuthorizationError(500, "AUTH_CLIENT_SECRET not configured — token exchange disabled")

    if client_secret != expected_secret:
        raise AuthorizationError(401, "Invalid client_secret")

    # Atomic one-shot consume — even on validation failure below, the code
    # can't be replayed (security > ergonomics here).
    # Redis TTL handles expiry automatically, so no explicit expires_at check.
    code_data = await _redis_pop(f"oidc:authz:{code}")
    if not code_data:
        raise AuthorizationError(400, "Invalid authorization code")

    if code_data["redirect_uri"] != redirect_uri:
        raise AuthorizationError(400, "Invalid redirect_uri")

    base_url = _get_glow_base_url()
    now = int(time.time())
    key_id = get_key_id()
    private_key = get_private_key()

    name = code_data.get("name", "")
    name_parts = name.split()
    given_name = name_parts[0] if name_parts else ""
    family_name = " ".join(name_parts[1:]) if len(name_parts) > 1 else ""

    profile_id = code_data.get("profile_id")
    sub = code_data.get("sub", "")
    if profile_id and not sub:
        sub = f"default_{profile_id}"

    id_token_payload = {
        "iss": base_url,
        "aud": client_id,
        "sub": sub,
        "exp": now + 3600,
        "iat": now,
        "email": code_data.get("email", ""),
        "email_verified": True,
        "name": name,
        "given_name": given_name,
        "family_name": family_name,
        "profile_id": profile_id,
        "role": code_data.get("role"),
        "is_emulation": code_data.get("is_emulation", False),
        "actor_profile_id": code_data.get("actor_profile_id"),
        "identity_provider": code_data.get("identity_provider"),
    }
    # Only include nonce if one was provided (browser OIDC may not send one)
    if code_data.get("nonce"):
        id_token_payload["nonce"] = code_data["nonce"]

    id_token = jwt.encode(
        id_token_payload,
        private_key,
        algorithm="RS256",
        headers={"kid": key_id},
    )

    access_token_payload = {
        "iss": base_url,
        "aud": client_id,
        "sub": sub,
        "exp": now + 3600,
        "iat": now,
        "scope": "openid profile email",
        "email": code_data.get("email", ""),
        "name": name,
        "given_name": given_name,
        "family_name": family_name,
        "profile_id": profile_id,
        "role": code_data.get("role"),
        "is_emulation": code_data.get("is_emulation", False),
        "actor_profile_id": code_data.get("actor_profile_id"),
        "identity_provider": code_data.get("identity_provider"),
    }

    access_token = jwt.encode(
        access_token_payload,
        private_key,
        algorithm="RS256",
        headers={"kid": key_id},
    )

    return {
        "access_token": access_token,
        "token_type": "Bearer",
        "id_token": id_token,
        "expires_in": 3600,
    }


def decode_userinfo(authorization: str) -> dict[str, Any]:
    """Decode access token and return user claims."""
    if not authorization or not authorization.startswith("Bearer "):
        raise AuthorizationError(401, "Missing or invalid authorization header")

    token = authorization[7:]

    try:
        payload = jwt.decode(
            token,
            key="",
            options={"verify_signature": False, "verify_aud": False},
        )
    except jwt.JWTError as e:
        raise AuthorizationError(401, f"Invalid token: {str(e)}")

    return {
        "sub": payload.get("sub"),
        "email": payload.get("email"),
        "name": payload.get("name"),
        "given_name": payload.get("given_name"),
        "family_name": payload.get("family_name"),
        "profile_id": payload.get("profile_id"),
        "role": payload.get("role"),
    }
