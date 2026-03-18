"""GET /login, /callback, /logout — Keycloak OAuth login flow."""

import logging
import os

import httpx
from fastapi import APIRouter, HTTPException
from fastapi.responses import RedirectResponse

from app.utils.auth.derive_key import derive_from_secret_key

logger = logging.getLogger(__name__)

router = APIRouter()

# --- config (resolved once at import) ---
_origin = os.getenv("ORIGIN", "http://localhost:3000")
_app_prefix = os.getenv("APP_PREFIX", "")
_keycloak_internal_url = os.getenv("KEYCLOAK_INTERNAL_URL", "http://localhost:8080")
_realm = os.getenv("KEYCLOAK_REALM", "master")
_client_id = os.getenv("AUTH_KEYCLOAK_ID", "glow-client")

_secret_key = os.getenv("SECRET_KEY")
_client_secret = os.getenv("AUTH_KEYCLOAK_SECRET") or (
    derive_from_secret_key(_secret_key, "keycloak-client") if _secret_key else None
)

# Browser-facing Keycloak base URL (through nginx in production)
_is_local = "localhost" in _origin
_browser_kc = (
    f"{_keycloak_internal_url}/auth" if _is_local else f"{_origin}{_app_prefix}/auth"
)

_redirect_uri = f"{_origin}{_app_prefix}/callback"


@router.get("/login")
async def login():
    """Redirect to Keycloak login page."""
    auth_url = (
        f"{_browser_kc}/realms/{_realm}/protocol/openid-connect/auth"
        f"?client_id={_client_id}"
        f"&response_type=code"
        f"&redirect_uri={_redirect_uri}"
        f"&scope=openid email profile"
    )
    return RedirectResponse(auth_url)


@router.get("/callback")
async def callback(code: str | None = None, error: str | None = None):
    """Handle Keycloak callback — exchange code for tokens."""
    if error:
        raise HTTPException(400, f"Login failed: {error}")
    if not code:
        raise HTTPException(400, "Missing authorization code")

    token_url = (
        f"{_keycloak_internal_url}/auth/realms/{_realm}"
        f"/protocol/openid-connect/token"
    )

    async with httpx.AsyncClient(timeout=15.0, verify=False) as client:
        resp = await client.post(
            token_url,
            data={
                "grant_type": "authorization_code",
                "client_id": _client_id,
                "client_secret": _client_secret,
                "code": code,
                "redirect_uri": _redirect_uri,
            },
        )

    if resp.status_code != 200:
        logger.error(f"Token exchange failed: {resp.status_code} {resp.text}")
        raise HTTPException(400, "Token exchange failed")

    tokens = resp.json()
    return {
        "access_token": tokens["access_token"],
        "token_type": "Bearer",
        "expires_in": tokens.get("expires_in"),
        "refresh_token": tokens.get("refresh_token"),
    }


@router.get("/logout")
async def logout():
    """Redirect to Keycloak logout, then back to login page."""
    logout_url = (
        f"{_browser_kc}/realms/{_realm}/protocol/openid-connect/logout"
        f"?post_logout_redirect_uri={_origin}{_app_prefix}/login"
        f"&client_id={_client_id}"
    )
    return RedirectResponse(logout_url)
