"""GET /default-idp/.well-known/openid-configuration — OIDC discovery."""

from typing import Any

from fastapi import APIRouter

from app.infra.identity.default_idp import get_openid_configuration

router = APIRouter()


@router.get("/.well-known/openid-configuration")
async def openid_configuration() -> dict[str, Any]:
    """OIDC discovery endpoint."""
    return get_openid_configuration()
