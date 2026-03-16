"""Default IdP business logic — authorization, token exchange, code store."""

import secrets
import time
from datetime import UTC, datetime
from typing import Any
from uuid import UUID

from jose import jwt

from app.infra.identity.jwks import get_key_id, get_private_key
from app.infra.identity.keycloak_sync import get_idp_public_url
from app.infra.profile_identity_context import resolve_profile_identity_context
from app.tools.entries.emulations.search import search_emulations
from app.tools.entries.grant_consumptions.create import create_grant_consumption
from app.tools.entries.grant_consumptions.search import search_grant_consumptions
from app.tools.entries.grants.get import get_grants

# In-memory store for authorization codes
_authorization_codes: dict[str, dict[str, Any]] = {}
_code_ttl = 600  # 10 minutes


def get_idp_base_url() -> str:
    """Get the base URL for the IdP (public URL for issuer)."""
    return get_idp_public_url()


def get_openid_configuration() -> dict[str, Any]:
    """Build the OIDC discovery document."""
    base_url = get_idp_base_url()
    return {
        "issuer": base_url,
        "authorization_endpoint": f"{base_url}/authorize",
        "token_endpoint": f"{base_url}/token",
        "jwks_uri": f"{base_url}/jwks",
        "userinfo_endpoint": f"{base_url}/userinfo",
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
        ],
    }


class AuthorizationError(Exception):
    """Raised when authorization fails with a specific HTTP status."""

    def __init__(self, status_code: int, detail: str) -> None:
        self.status_code = status_code
        self.detail = detail
        super().__init__(detail)


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
            grants = await get_grants(conn, ids=[emulation_grant])
            if not grants:
                raise AuthorizationError(404, "Emulation grant not found.")

            grant = grants[0]
            if grant.expires_at <= datetime.now(UTC):
                raise AuthorizationError(403, "Grant expired.")

            consumptions = await search_grant_consumptions(
                conn, grant_ids=[emulation_grant], limit=1
            )
            if consumptions:
                raise AuthorizationError(403, "Grant already used.")

            await create_grant_consumption(conn, grant_id=emulation_grant)
            actor_profile_id = grant.profiles_id

            emulations = await search_emulations(
                conn, grant_ids=[emulation_grant], limit=1
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
    expires_at = int(time.time()) + _code_ttl

    is_emulation = emulation_grant is not None
    _authorization_codes[code] = {
        "profile_id": str(resolved_profile_id),
        "email": resolved_email,
        "name": profile.name or "",
        "role": profile.role if profile.role else None,
        "nonce": nonce,
        "expires_at": expires_at,
        "client_id": client_id,
        "redirect_uri": redirect_uri,
        "is_emulation": is_emulation,
        "actor_profile_id": str(actor_profile_id) if actor_profile_id else None,
    }

    # Garbage-collect expired codes
    current_time = int(time.time())
    expired_codes = [
        k for k, v in _authorization_codes.items() if v["expires_at"] < current_time
    ]
    for expired_code in expired_codes:
        del _authorization_codes[expired_code]

    return f"{redirect_uri}?code={code}&state={state}"


def exchange_code_for_tokens(
    *,
    grant_type: str,
    code: str,
    redirect_uri: str,
    client_id: str,
) -> dict[str, Any]:
    """Exchange authorization code for access + id tokens.

    Returns the token response dict.
    Raises AuthorizationError on validation failures.
    """
    if grant_type != "authorization_code":
        raise AuthorizationError(
            400,
            f"Unsupported grant_type: {grant_type}. Only 'authorization_code' is supported.",
        )

    code_data = _authorization_codes.get(code)
    if not code_data:
        raise AuthorizationError(400, "Invalid authorization code")

    if code_data["expires_at"] < int(time.time()):
        del _authorization_codes[code]
        raise AuthorizationError(400, "Authorization code has expired")

    if code_data["client_id"] != client_id:
        raise AuthorizationError(400, "Invalid client_id")

    if code_data["redirect_uri"] != redirect_uri:
        raise AuthorizationError(400, "Invalid redirect_uri")

    del _authorization_codes[code]

    base_url = get_idp_base_url()
    now = int(time.time())
    key_id = get_key_id()
    private_key = get_private_key()

    name = code_data["name"]
    name_parts = name.split()
    given_name = name_parts[0] if name_parts else ""
    family_name = " ".join(name_parts[1:]) if len(name_parts) > 1 else ""

    sub = f"default_{code_data['profile_id']}"

    id_token_payload = {
        "iss": base_url,
        "aud": client_id,
        "sub": sub,
        "exp": now + 3600,
        "iat": now,
        "nonce": code_data["nonce"],
        "email": code_data["email"],
        "email_verified": True,
        "name": name,
        "given_name": given_name,
        "family_name": family_name,
        "profile_id": code_data["profile_id"],
        "role": code_data.get("role"),
        "is_emulation": code_data.get("is_emulation", False),
        "actor_profile_id": code_data.get("actor_profile_id"),
    }

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
        "email": code_data["email"],
        "name": name,
        "given_name": given_name,
        "family_name": family_name,
        "profile_id": code_data["profile_id"],
        "role": code_data.get("role"),
        "is_emulation": code_data.get("is_emulation", False),
        "actor_profile_id": code_data.get("actor_profile_id"),
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
    """Decode access token and return user claims.

    Raises AuthorizationError on invalid/missing token.
    """
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
    }
