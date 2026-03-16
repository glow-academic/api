"""OAuth middleware for MCP server — Keycloak integration.

Handles:
  - OAuth discovery endpoints (RFC 8414, RFC 9728)
  - Bearer token verification (delegates to resolve_identity.verify_jwt)
  - Profile resolution from JWT claims (delegates to resolve_identity._resolve_profile_id)
  - Feature flag gating (is_mcp_enabled)
  - Path rewriting for Cursor/ChatGPT compatibility
"""

import logging
import os
from typing import Any

from fastapi import Request, Response, status
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware

logger = logging.getLogger(__name__)

# Configuration from environment
ORIGIN = os.getenv("ORIGIN", "http://localhost")
APP_PREFIX = os.getenv("APP_PREFIX", "")
KEYCLOAK_REALM = os.getenv("KEYCLOAK_REALM", "master")

# Detect local dev environment
origin_check = os.getenv("ORIGIN", "http://localhost:3000")
is_local_dev = "localhost" in origin_check.lower()

# MCP resource URL - use server port (8000) in dev, ORIGIN in prod
MCP_SERVER_BASE = "http://localhost:8000" if is_local_dev else ORIGIN
MCP_RESOURCE = f"{MCP_SERVER_BASE}{APP_PREFIX}/mcp"
KEYCLOAK_ISSUER = f"{ORIGIN}{APP_PREFIX}/auth/realms/{KEYCLOAK_REALM}"


def is_mcp_enabled() -> bool:
    """Check if MCP is enabled (hardcoded for now, ready for DB integration)."""
    return True


def oauth_401() -> Response:
    """Return 401 with WWW-Authenticate header per RFC 9728."""
    prm_endpoint = f"{ORIGIN}{APP_PREFIX}/.well-known/oauth-protected-resource"
    auth_endpoint = f"{KEYCLOAK_ISSUER}/protocol/openid-connect/auth"
    return Response(
        status_code=status.HTTP_401_UNAUTHORIZED,
        headers={
            "WWW-Authenticate": (
                f'Bearer realm="mcp", resource="{MCP_RESOURCE}", '
                f'resource_metadata="{prm_endpoint}", '
                f'authorization_uri="{auth_endpoint}", '
                f'scope="mcp-resource"'
            )
        },
    )


# Shared scope lists for discovery endpoints
_SCOPES_SUPPORTED = [
    "openid",
    "profile",
    "email",
    "address",
    "phone",
    "offline_access",
    "organization",
    "microprofile-jwt",
    "mcp-resource",
]


class McpOAuthMiddleware(BaseHTTPMiddleware):
    """Middleware for MCP OAuth authentication and feature flag gating."""

    async def dispatch(self, request: Request, call_next: Any) -> Response:
        # Allow CORS preflight
        if request.method == "OPTIONS":
            return await call_next(request)

        path = request.url.path

        # --- OAuth discovery endpoints (no auth required) ---

        oauth_as_path = (
            f"{APP_PREFIX}/.well-known/oauth-authorization-server"
            if APP_PREFIX
            else "/.well-known/oauth-authorization-server"
        )

        if path == oauth_as_path:
            return JSONResponse(
                {
                    "issuer": KEYCLOAK_ISSUER,
                    "authorization_endpoint": f"{KEYCLOAK_ISSUER}/protocol/openid-connect/auth",
                    "token_endpoint": f"{KEYCLOAK_ISSUER}/protocol/openid-connect/token",
                    "registration_endpoint": f"{KEYCLOAK_ISSUER}/clients-registrations/openid-connect",
                    "scopes_supported": _SCOPES_SUPPORTED,
                    "response_types_supported": ["code"],
                    "grant_types_supported": ["authorization_code"],
                    "token_endpoint_auth_methods_supported": [
                        "client_secret_post",
                        "client_secret_basic",
                    ],
                    "code_challenge_methods_supported": ["S256"],
                }
            )

        # --- PRM discovery (RFC 9728) ---

        mcp_path = f"{APP_PREFIX}/mcp" if APP_PREFIX else "/mcp"
        prm_path = (
            f"{APP_PREFIX}/.well-known/oauth-protected-resource"
            if APP_PREFIX
            else "/.well-known/oauth-protected-resource"
        )
        mcp_prm_path = f"{mcp_path}/.well-known/oauth-protected-resource"

        if (
            path == prm_path
            or path == mcp_prm_path
            or path.endswith("/.well-known/oauth-protected-resource")
            or path == "/.well-known/oauth-protected-resource/mcp"
            or (
                path.startswith("/.well-known/oauth-protected-resource/")
                and path.endswith("/mcp")
            )
        ):
            return JSONResponse(
                {
                    "resource": MCP_RESOURCE,
                    "authorization_servers": [KEYCLOAK_ISSUER],
                    "code_challenge_methods_supported": ["S256"],
                    "scopes_supported": _SCOPES_SUPPORTED,
                }
            )

        # --- Only process /mcp paths from here ---

        if not path.startswith(mcp_path) and not path.startswith("/mcp"):
            return await call_next(request)

        # Rewrite /mcp/sse/ → /mcp for FastMCP
        if path == f"{mcp_path}/sse/" or path == "/mcp/sse/":
            request.scope["path"] = mcp_path
            request.scope["raw_path"] = mcp_path.encode()

        # Feature flag
        if not is_mcp_enabled():
            return JSONResponse(
                {"error": "mcp_disabled", "message": "MCP is currently disabled."},
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                headers={"Retry-After": "300"},
            )

        # --- Bearer token verification (reuses resolve_identity.verify_jwt) ---

        from app.infra.identity.resolve_identity import (
            _resolve_profile_id,
            extract_bearer_token,
            verify_jwt,
        )

        token = extract_bearer_token(request.headers.get("authorization"))
        if not token:
            logger.info(
                f"MCP request missing Authorization header: "
                f"{request.method} {path}"
            )
            return oauth_401()

        try:
            claims = verify_jwt(token)
            logger.debug(
                f"MCP OAuth token validated: "
                f"sub={claims.get('sub')}, azp={claims.get('azp')}"
            )
        except ValueError as e:
            logger.warning(f"MCP OAuth token validation failed: {e}")
            return oauth_401()

        # --- Profile resolution (reuses resolve_identity._resolve_profile_id) ---

        from app.infra.globals import get_pool

        pool = get_pool()
        if pool:
            try:
                profile_id = await _resolve_profile_id(claims, pool)
                if profile_id:
                    request.state.profile_id = str(profile_id)
                    from app.utils.logging.db_logger import set_profile_id

                    set_profile_id(str(profile_id))
                    logger.debug(f"MCP profile resolved: {profile_id}")
                else:
                    logger.warning(
                        f"MCP token valid but no profile for email: "
                        f"{claims.get('email')}"
                    )
            except Exception as e:
                logger.error(
                    f"Failed to resolve MCP profile: {e}", exc_info=True
                )

        # Rewrite Cursor-style paths → /mcp for FastMCP
        if path in [
            f"{mcp_path}/messages",
            f"{mcp_path}/sse/messages",
            "/mcp/messages",
            "/mcp/sse/messages",
        ]:
            request.scope["path"] = mcp_path
            request.scope["raw_path"] = mcp_path.encode()

        return await call_next(request)
