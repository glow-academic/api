"""POST /token — OIDC token exchange endpoint."""

import base64
from typing import Any
from urllib.parse import unquote

from fastapi import APIRouter, HTTPException, Request

from app.infra.identity.default_idp import (
    AuthorizationError,
    exchange_code_for_tokens,
    refresh_tokens,
)
from app.utils.error.handle_route_error import handle_route_error

router = APIRouter()


@router.post("/token")
async def token(request: Request) -> dict[str, Any]:
    """Token endpoint — exchanges authorization codes (or refresh tokens) for tokens.

    Supports client_secret_post (form body) and client_secret_basic (Authorization header).
    """
    form = await request.form()

    # These are always application/x-www-form-urlencoded strings; coerce away
    # the Starlette `str | UploadFile | None` form-value type so the values
    # flow cleanly into the str-typed token helpers.
    def _field(key: str) -> str:
        value = form.get(key, "")
        return value if isinstance(value, str) else ""

    grant_type = _field("grant_type")
    code = _field("code")
    redirect_uri = _field("redirect_uri")
    refresh_token = _field("refresh_token")
    client_id = _field("client_id")
    client_secret = _field("client_secret")

    if not grant_type:
        raise HTTPException(400, "Missing required field: grant_type")
    if grant_type == "refresh_token":
        if not refresh_token:
            raise HTTPException(400, "Missing required field: refresh_token")
    elif not code or not redirect_uri:
        raise HTTPException(400, "Missing required fields: code, redirect_uri")

    # Extract client_id/client_secret from Basic Auth header if not in form.
    # Per RFC 6749 §2.3.1, both halves are application/x-www-form-urlencoded
    # *before* base64 — secrets with `=` / `+` / `/` (common in base64
    # payloads) arrive as %3D / %2B / %2F and must be URL-decoded back
    # before string comparison.
    auth_header = request.headers.get("authorization", "")
    if auth_header.startswith("Basic "):
        try:
            decoded = base64.b64decode(auth_header[6:]).decode()
            basic_id, basic_secret = decoded.split(":", 1)
            if not client_id:
                client_id = unquote(basic_id)
            if not client_secret:
                client_secret = unquote(basic_secret)
        except Exception:
            pass

    if not client_id:
        raise HTTPException(400, "client_id is required")

    try:
        if grant_type == "refresh_token":
            return await refresh_tokens(
                refresh_token=refresh_token,
                client_id=client_id,
                client_secret=client_secret,
            )
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
