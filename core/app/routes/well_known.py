"""RFC 8414 OAuth Authorization Server Metadata endpoint."""

from fastapi import APIRouter

from app.infra.identity.default_idp import get_openid_configuration

router = APIRouter()


@router.get("/.well-known/oauth-authorization-server")
def oauth_authorization_server_metadata():
    """RFC 8414 OAuth Authorization Server Metadata — same as OIDC discovery."""
    return get_openid_configuration()
