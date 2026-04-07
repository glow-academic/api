"""GET /default-idp/.well-known/openid-configuration — OIDC discovery."""

from typing import Any

from fastapi import APIRouter, Request

from app.infra.identity.default_idp import get_openid_configuration

router = APIRouter()


@router.get("/.well-known/openid-configuration")
async def openid_configuration(request: Request) -> dict[str, Any]:
    """OIDC discovery endpoint.

    Returns endpoints relative to the request's base URL so discovery
    works over both the public URL and the internal Docker network.
    """
    # Use the request's scheme+host as base when it differs from ORIGIN
    # (e.g., internal Docker network: http://glow-api:8000)
    host = request.headers.get("host", "")
    scheme = request.headers.get("x-forwarded-proto", request.url.scheme)
    request_base = f"{scheme}://{host}" if host else None
    return get_openid_configuration(base_url_override=request_base)
