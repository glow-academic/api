"""GET /authorize + GET /oidc-callback — OIDC authorization with Keycloak intermediary.

Standard OIDC flow (no profile_id):
  1. CLI calls /authorize → saves session, redirects to Keycloak
  2. User authenticates in Keycloak
  3. Keycloak redirects to /oidc-callback with Keycloak code
  4. /oidc-callback exchanges Keycloak code server-to-server, issues glow-api code
  5. CLI exchanges glow-api code at /token

Keycloak broker flow (with profile_id):
  Keycloak calls /authorize?profile_id=X → issues code directly.
"""

import os
import secrets as _secrets
from urllib.parse import urlencode
from uuid import UUID

import httpx
import jwt as pyjwt
from fastapi import APIRouter, HTTPException, Query, Request
from fastapi.responses import RedirectResponse

from app.infra.globals import get_pool, get_redis_client
from app.infra.identity.default_idp import (
    AuthorizationError,
    resolve_authorization,
    _authorization_codes,
)
from app.infra.identity.jwks import get_key_id, get_private_key
from app.utils.auth.derive_key import derive_from_secret_key
from app.utils.error.handle_route_error import handle_route_error

router = APIRouter()

_ORIGIN = os.getenv("ORIGIN", "http://localhost")
_APP_PREFIX = os.getenv("APP_PREFIX", "")
_KC_REALM = os.getenv("KEYCLOAK_REALM", "master")
_KC_CLIENT_ID = os.getenv("AUTH_KEYCLOAK_ID", "glow-client")
_KC_INTERNAL_URL = os.getenv("KEYCLOAK_INTERNAL_URL", "http://keycloak:8080")

# In-memory pending sessions (like LearnLoop's _pending_sessions)
_pending_sessions: dict[str, dict] = {}


def _get_kc_client_secret() -> str:
    """Get the Keycloak client secret (derived from SECRET_KEY)."""
    secret = os.getenv("AUTH_KEYCLOAK_SECRET")
    if not secret:
        sk = os.getenv("SECRET_KEY", "")
        if sk:
            secret = derive_from_secret_key(sk, "keycloak-client")
    return secret or ""


@router.get("/authorize")
async def authorize(
    request: Request,
    client_id: str = Query(...),
    redirect_uri: str = Query(...),
    response_type: str = Query(...),
    state: str = Query(...),
    scope: str = Query("openid profile email"),
    nonce: str | None = Query(None),
    profile_id: UUID | None = Query(None),
    emulation_grant: UUID | None = Query(None),
    login_hint: str | None = Query(None),
) -> RedirectResponse:
    """Authorization endpoint.

    Without profile_id: standard OIDC — saves session, redirects to Keycloak.
    With profile_id: Keycloak broker callback — issues authorization code directly.
    """
    # Standard OIDC flow: no profile_id → intermediary through Keycloak
    if profile_id is None and emulation_grant is None and login_hint is None:
        # Save the CLI's redirect_uri and state so we can redirect back after Keycloak
        internal_state = _secrets.token_urlsafe(32)
        _pending_sessions[internal_state] = {
            "redirect_uri": redirect_uri,
            "state": state,
            "nonce": nonce,
            "client_id": client_id,
        }

        # Redirect to Keycloak with our own /oidc-callback as redirect_uri
        callback_uri = f"{_ORIGIN}{_APP_PREFIX}/oidc-callback"
        kc_auth_url = f"{_ORIGIN}{_APP_PREFIX}/auth/realms/{_KC_REALM}/protocol/openid-connect/auth"
        params = urlencode({
            "response_type": "code",
            "client_id": _KC_CLIENT_ID,
            "redirect_uri": callback_uri,
            "scope": scope,
            "state": internal_state,
        })
        return RedirectResponse(url=f"{kc_auth_url}?{params}")

    # Keycloak broker flow: profile_id present → resolve and issue code
    try:
        pool = get_pool()
        redis = get_redis_client()
        redirect_url = await resolve_authorization(
            pool,
            redis,
            response_type=response_type,
            client_id=client_id,
            redirect_uri=redirect_uri,
            state=state,
            nonce=nonce,
            profile_id=profile_id,
            emulation_grant=emulation_grant,
            login_hint=login_hint,
        )
        return RedirectResponse(url=redirect_url)
    except AuthorizationError as e:
        raise HTTPException(status_code=e.status_code, detail=e.detail)
    except HTTPException:
        raise
    except Exception as e:
        handle_route_error(
            error=e,
            route_path=request.url.path,
            operation="authorize",
            request=request,
        )


@router.get("/oidc-callback")
async def oidc_callback(
    code: str | None = None,
    state: str | None = None,
    error: str | None = None,
):
    """Handle Keycloak callback: exchange code, create glow-api auth code, redirect to CLI."""
    if error:
        raise HTTPException(400, f"Login failed: {error}")
    if not code or not state:
        raise HTTPException(400, "Missing code or state")

    session = _pending_sessions.pop(state, None)
    if not session:
        raise HTTPException(400, "Invalid or expired session")

    # Exchange Keycloak's code for tokens (server-to-server)
    callback_uri = f"{_ORIGIN}{_APP_PREFIX}/oidc-callback"
    token_url = f"{_KC_INTERNAL_URL}/auth/realms/{_KC_REALM}/protocol/openid-connect/token"
    kc_secret = _get_kc_client_secret()

    async with httpx.AsyncClient(timeout=15.0) as http:
        resp = await http.post(token_url, data={
            "grant_type": "authorization_code",
            "client_id": _KC_CLIENT_ID,
            "client_secret": kc_secret,
            "code": code,
            "redirect_uri": callback_uri,
        })

    if resp.status_code != 200:
        raise HTTPException(400, "Token exchange with identity provider failed")

    # Decode Keycloak's access token to get user claims (trusted — direct from Keycloak)
    kc_claims = pyjwt.decode(resp.json()["access_token"], options={"verify_signature": False})

    # Create a glow-api authorization code
    import time
    glow_code = _secrets.token_urlsafe(32)
    _authorization_codes[glow_code] = {
        "profile_id": kc_claims.get("profile_id", kc_claims.get("sub", "")),
        "email": kc_claims.get("email", ""),
        "name": kc_claims.get("name", kc_claims.get("preferred_username", "")),
        "role": kc_claims.get("role", kc_claims.get("realm_access", {}).get("roles", [None])[0]),
        "nonce": session.get("nonce"),
        "expires_at": int(time.time()) + 600,
        "client_id": session["client_id"],
        "redirect_uri": session["redirect_uri"],
        "is_emulation": False,
        "actor_profile_id": None,
    }

    # Redirect back to the CLI's original callback
    redirect_params = {"code": glow_code}
    if session.get("state"):
        redirect_params["state"] = session["state"]

    target = f"{session['redirect_uri']}?{urlencode(redirect_params)}"
    return RedirectResponse(target, status_code=302)
