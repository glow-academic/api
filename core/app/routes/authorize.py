"""GET /authorize — OIDC authorization endpoint.

Standard OIDC flow: redirects to Keycloak login page.
Keycloak broker flow: profile_id present, issues code directly.
"""

import os
from urllib.parse import urlencode
from uuid import UUID

from fastapi import APIRouter, HTTPException, Query, Request
from fastapi.responses import RedirectResponse

from app.infra.globals import get_pool, get_redis_client
from app.infra.identity.default_idp import AuthorizationError, resolve_authorization
from app.utils.error.handle_route_error import handle_route_error

router = APIRouter()

_ORIGIN = os.getenv("ORIGIN", "http://localhost")
_APP_PREFIX = os.getenv("APP_PREFIX", "")
_KC_REALM = os.getenv("KEYCLOAK_REALM", "master")
_KC_CLIENT_ID = os.getenv("AUTH_KEYCLOAK_ID", "glow-client")


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

    Without profile_id: standard OIDC — redirects to Keycloak login page.
    With profile_id: Keycloak broker callback — issues authorization code.
    """
    # Standard OIDC flow: no profile_id → redirect to Keycloak login
    if profile_id is None and emulation_grant is None and login_hint is None:
        kc_auth_url = f"{_ORIGIN}{_APP_PREFIX}/auth/realms/{_KC_REALM}/protocol/openid-connect/auth"
        params = urlencode({
            "client_id": _KC_CLIENT_ID,
            "redirect_uri": redirect_uri,
            "response_type": response_type,
            "state": state,
            "scope": scope,
            **({"nonce": nonce} if nonce else {}),
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
