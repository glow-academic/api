"""GET /default-idp/jwks — JWKS public key endpoint."""

from fastapi import APIRouter

from app.infra.identity.jwks import get_jwks

router = APIRouter()


@router.get("/jwks")
async def jwks_endpoint():
    """JWKS endpoint for public key exposure."""
    return get_jwks()
