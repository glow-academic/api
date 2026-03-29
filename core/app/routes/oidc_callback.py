"""GET /oidc-callback — Handle Keycloak's redirect after browser login.

Part of the OIDC proxy flow:
  1. Client → /authorize → Keycloak
  2. User authenticates at Keycloak
  3. Keycloak → /oidc-callback (this endpoint)
  4. Exchange Keycloak's code → issue Glow's auth code → redirect to client
"""

from fastapi import APIRouter, HTTPException, Query, Request
from fastapi.responses import RedirectResponse

from app.infra.identity.default_idp import AuthorizationError, handle_oidc_callback
from app.utils.error.handle_route_error import handle_route_error

router = APIRouter()


@router.get("/oidc-callback")
async def oidc_callback(
    request: Request,
    code: str | None = Query(None),
    state: str | None = Query(None),
    error: str | None = Query(None),
    error_description: str | None = Query(None),
) -> RedirectResponse:
    """Handle Keycloak's redirect back after user authentication."""
    if error:
        detail = error_description or error
        raise HTTPException(400, f"Login failed: {detail}")
    if not code or not state:
        raise HTTPException(400, "Missing code or state from identity provider")

    try:
        redirect_url = await handle_oidc_callback(code=code, state=state)
        return RedirectResponse(url=redirect_url, status_code=302)
    except AuthorizationError as e:
        raise HTTPException(status_code=e.status_code, detail=e.detail)
    except HTTPException:
        raise
    except Exception as e:
        handle_route_error(
            error=e,
            route_path=request.url.path,
            operation="oidc_callback",
            request=request,
        )
