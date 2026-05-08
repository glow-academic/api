"""GET /login, /callback, /logout, /me — Keycloak OAuth login flow."""

import os

import httpx
from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import RedirectResponse

from app.infra.identity.middleware import require_auth
from app.infra.identity.resolve_identity import Identity
from app.utils.logging.db_logger import get_logger

logger = get_logger(__name__)

router = APIRouter()

# --- config (resolved once at import) ---
_origin = os.getenv("ORIGIN", "http://localhost:3000")
_app_prefix = os.getenv("APP_PREFIX", "")
_keycloak_internal_url = os.getenv("KEYCLOAK_INTERNAL_URL", "http://localhost:8080")
_realm = os.getenv("KEYCLOAK_REALM", "master")
_client_id = os.getenv("AUTH_KEYCLOAK_ID", "glow-client")
_auth_client_secret = os.getenv("AUTH_CLIENT_SECRET", "")
_deployment_token = os.getenv("DEPLOYMENT_TOKEN", "")

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
                "client_secret": _auth_client_secret,
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
async def logout(
    post_logout_redirect_uri: str | None = None,
    client_id: str | None = None,
    id_token_hint: str | None = None,
):
    """OIDC end_session_endpoint — proxy logout to Keycloak.

    The client sends a Glow-signed id_token_hint. We look up the
    corresponding KC-signed id_token (stored during login) and pass
    that to Keycloak so it can do a silent logout without confirmation.
    """
    from app.infra.identity.default_idp import get_kc_id_token_for_logout

    redirect_uri = post_logout_redirect_uri or f"{_origin}{_app_prefix}/login"
    logout_url = (
        f"{_browser_kc}/realms/{_realm}/protocol/openid-connect/logout"
        f"?post_logout_redirect_uri={redirect_uri}"
        f"&client_id={client_id or _client_id}"
    )
    # Translate Glow id_token → KC id_token for silent logout
    kc_token = await get_kc_id_token_for_logout(id_token_hint)
    if kc_token:
        logout_url += f"&id_token_hint={kc_token}"
    return RedirectResponse(logout_url)


@router.get("/me")
async def me(identity: Identity = Depends(require_auth)):
    """Return current authenticated user info."""
    return {
        "profile_id": str(identity.profile_id),
        "session_id": str(identity.session_id),
        "email": identity.email,
        "role": identity.role,
        "is_emulation": identity.is_emulation,
        "actor_profile_id": str(identity.actor_profile_id) if identity.actor_profile_id else None,
    }


@router.get("/auth/client-config")
async def client_config(request: Request):
    """Return OAuth client credentials for frontend integration.

    Authenticated by deployment token (managed or self-hosted).
    Any frontend (Next.js, React, mobile) can call this to get
    the credentials needed to connect to this server's auth.

    Like Google/Microsoft OAuth: you get a client_id + secret,
    plug them into your app, done.
    """
    from fastapi import Request as _  # already imported above

    auth = request.headers.get("Authorization", "")
    if not auth.startswith("Bearer "):
        raise HTTPException(401, "Missing deployment token")

    token = auth[7:]

    # Accept deployment token (exact match) or admin JWT
    if token == _deployment_token:
        pass  # deployment token verified
    else:
        # Try verifying as admin JWT
        try:
            identity = await require_auth(request=request, authorization=f"Bearer {token}")
            if identity.role not in ("admin", "owner"):
                raise HTTPException(403, "Admin access required")
        except Exception:
            raise HTTPException(401, "Invalid deployment token or admin credentials")

    if not _auth_client_secret:
        raise HTTPException(500, "Server auth not configured (missing AUTH_CLIENT_SECRET)")

    return {
        "auth_url": f"{_origin}{_app_prefix}/auth",
        "realm": _realm,
        "client_id": _client_id,
        "client_secret": _auth_client_secret,
        "issuer": f"{_origin}{_app_prefix}/auth/realms/{_realm}",
    }
