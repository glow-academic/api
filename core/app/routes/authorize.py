"""GET /authorize — OIDC authorization endpoint.

Supports two flows:
  1. Standard OIDC (no profile_id): saves session → redirects to Keycloak
  2. Profile login (with profile_id): Keycloak broker callback → issues code directly
"""

from uuid import UUID

from fastapi import APIRouter, HTTPException, Query, Request
from fastapi.responses import RedirectResponse

from app.infra.globals import get_pool, get_redis_client
from app.infra.identity.default_idp import (
    AuthorizationError,
    create_browser_session,
    resolve_authorization,
)
from app.utils.error.handle_route_error import handle_route_error

router = APIRouter()


@router.get("/authorize")
async def authorize(
    request: Request,
    client_id: str = Query(...),
    redirect_uri: str = Query(...),
    response_type: str = Query(...),
    state: str = Query(""),
    scope: str = Query("openid profile email"),
    nonce: str | None = Query(None),
    profile_id: UUID | None = Query(None),
    emulation_grant: UUID | None = Query(None),
    login_hint: str | None = Query(None),
) -> RedirectResponse:
    """OIDC authorization endpoint.

    Without profile_id: standard OIDC flow — redirect to Keycloak for login.
    With profile_id: Keycloak broker callback — issue auth code directly.
    """
    try:
        # Flow 1: Standard OIDC (client initiated, no profile_id)
        if profile_id is None and emulation_grant is None and login_hint is None:
            redirect_url = create_browser_session(
                redirect_uri=redirect_uri,
                state=state,
                nonce=nonce,
                client_id=client_id,
            )
            return RedirectResponse(url=redirect_url)

        # Flow 2: Profile login (Keycloak broker callback)
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
