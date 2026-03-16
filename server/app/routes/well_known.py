"""RFC 8414 OAuth Authorization Server Metadata endpoint."""

import os

from fastapi import APIRouter

router = APIRouter()


@router.get("/.well-known/oauth-authorization-server")
def oauth_authorization_server_metadata():
    """RFC 8414 OAuth Authorization Server Metadata endpoint."""
    ORIGIN = os.getenv("ORIGIN", "http://localhost")
    APP_PREFIX = os.getenv("APP_PREFIX", "")
    KEYCLOAK_REALM = os.getenv("KEYCLOAK_REALM", "master")
    KEYCLOAK_ISSUER = f"{ORIGIN}{APP_PREFIX}/auth/realms/{KEYCLOAK_REALM}"
    return {
        "issuer": KEYCLOAK_ISSUER,
        "authorization_endpoint": f"{KEYCLOAK_ISSUER}/protocol/openid-connect/auth",
        "token_endpoint": f"{KEYCLOAK_ISSUER}/protocol/openid-connect/token",
        "scopes_supported": [
            "openid",
            "profile",
            "email",
            "address",
            "phone",
            "offline_access",
            "organization",
            "microprofile-jwt",
            "mcp-resource",
        ],
        "response_types_supported": ["code"],
        "grant_types_supported": ["authorization_code"],
        "token_endpoint_auth_methods_supported": [
            "client_secret_post",
            "client_secret_basic",
        ],
        "code_challenge_methods_supported": ["S256"],
    }
