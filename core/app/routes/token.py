"""POST /default-idp/token — OIDC token exchange endpoint."""

from typing import Any

from fastapi import APIRouter, Form, HTTPException, Request

from app.infra.identity.default_idp import AuthorizationError, exchange_code_for_tokens
from app.utils.error.handle_route_error import handle_route_error

router = APIRouter()


@router.post("/token")
async def token(
    request: Request,
    grant_type: str = Form(...),
    code: str = Form(...),
    redirect_uri: str = Form(...),
    client_id: str = Form(...),
    client_secret: str = Form(None),
) -> dict[str, Any]:
    """Token endpoint — exchanges authorization codes for tokens."""
    try:
        return exchange_code_for_tokens(
            grant_type=grant_type,
            code=code,
            redirect_uri=redirect_uri,
            client_id=client_id,
        )
    except AuthorizationError as e:
        raise HTTPException(status_code=e.status_code, detail=e.detail)
    except HTTPException:
        raise
    except Exception as e:
        handle_route_error(
            error=e,
            route_path=request.url.path,
            operation="token",
            request=request,
        )
