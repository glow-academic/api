"""GET /default-idp/userinfo — OIDC userinfo endpoint."""

from typing import Any

from fastapi import APIRouter, Header, HTTPException, Request

from app.infra.identity.default_idp import AuthorizationError, decode_userinfo
from app.utils.error.handle_route_error import handle_route_error

router = APIRouter()


@router.get("/userinfo")
async def userinfo(
    request: Request,
    authorization: str | None = Header(None),
) -> dict[str, Any]:
    """UserInfo endpoint — returns user claims from access token."""
    try:
        return decode_userinfo(authorization)
    except AuthorizationError as e:
        raise HTTPException(status_code=e.status_code, detail=e.detail)
    except HTTPException:
        raise
    except Exception as e:
        handle_route_error(
            error=e,
            route_path=request.url.path,
            operation="userinfo",
            request=request,
        )
