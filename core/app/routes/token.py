"""POST /token — OIDC token exchange endpoint."""

import base64
from typing import Any

from fastapi import APIRouter, HTTPException, Request

from app.infra.identity.default_idp import AuthorizationError, exchange_code_for_tokens
from app.utils.error.handle_route_error import handle_route_error

router = APIRouter()


@router.post("/token")
async def token(request: Request) -> dict[str, Any]:
    """Token endpoint — exchanges authorization codes for tokens.

    Supports client_secret_post (form body) and client_secret_basic (Authorization header).
    """
    form = await request.form()
    grant_type = form.get("grant_type")
    code = form.get("code")
    redirect_uri = form.get("redirect_uri")
    client_id = form.get("client_id", "")
    client_secret = form.get("client_secret", "")

    if not grant_type or not code or not redirect_uri:
        raise HTTPException(400, "Missing required fields: grant_type, code, redirect_uri")

    # Extract client_id/client_secret from Basic Auth header if not in form
    auth_header = request.headers.get("authorization", "")
    if auth_header.startswith("Basic "):
        try:
            decoded = base64.b64decode(auth_header[6:]).decode()
            basic_id, basic_secret = decoded.split(":", 1)
            if not client_id:
                client_id = basic_id
            if not client_secret:
                client_secret = basic_secret
        except Exception:
            pass

    if not client_id:
        raise HTTPException(400, "client_id is required")

    try:
        return await exchange_code_for_tokens(
            grant_type=grant_type,
            code=code,
            redirect_uri=redirect_uri,
            client_id=client_id,
            client_secret=client_secret,
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
