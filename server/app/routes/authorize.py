"""GET /default-idp/authorize — OIDC authorization endpoint."""

from uuid import UUID

from fastapi import APIRouter, HTTPException, Query, Request
from fastapi.responses import RedirectResponse

from app.infra.globals import get_pool, get_redis_client
from app.infra.identity.default_idp import AuthorizationError, resolve_authorization
from app.utils.error.handle_route_error import handle_route_error

router = APIRouter()


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
    """Authorization endpoint — handles Keycloak broker redirects."""
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
