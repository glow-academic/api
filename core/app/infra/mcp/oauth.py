"""OAuth middleware for MCP server — Keycloak integration.

Handles:
  - OAuth discovery endpoints (RFC 8414, RFC 9728)
  - Bearer token verification (delegates to resolve_identity.verify_jwt)
  - Profile resolution from JWT claims (delegates to resolve_identity._resolve_profile_id)
  - Feature flag gating (is_mcp_enabled)
  - Path rewriting for Cursor/ChatGPT compatibility
"""

import asyncio
import os
from typing import Any

from fastapi import Request, Response, status
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware

from app.utils.logging.db_logger import get_logger

logger = get_logger(__name__)

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

# Keycloak issuer advertised in PRM + AS metadata.
# Locally Keycloak is direct on :8080 (no reverse proxy), so the PRM must
# advertise that host — otherwise OAuth clients (Claude Code, MCP Inspector,
# etc.) follow the advertised URL and 404 at the frontend port.
# In prod, the reverse proxy at ORIGIN routes /auth/* to Keycloak.
KEYCLOAK_BASE = "http://localhost:8080" if is_local_dev else ORIGIN
KEYCLOAK_ISSUER = f"{KEYCLOAK_BASE}{APP_PREFIX}/auth/realms/{KEYCLOAK_REALM}"


def is_mcp_enabled() -> bool:
    """Check if MCP is enabled (hardcoded for now, ready for DB integration)."""
    return True


def _token_shape(token: str | None) -> str:
    """Describe a token's shape without leaking its value.

    Used when verify_jwt fails so we can distinguish an opaque Keycloak
    reference token from a malformed/empty JWT from a truncated string.
    """
    if not token:
        return "empty"
    parts = token.split(".")
    prefix = token[:10]
    return (
        f"len={len(token)} segments={len(parts)} "
        f"starts_with_eyJ={token.startswith('eyJ')} prefix={prefix!r}"
    )


def _get_base_url(request: Request | None = None) -> str:
    """Get the base URL from the request's forwarded host, falling back to ORIGIN.

    This allows MCP endpoints to work when accessed through different domains
    (e.g., docs domain proxying to the API). The OAuth discovery URLs will
    match the domain the client actually connected to.
    """
    if request:
        forwarded_host = request.headers.get("x-forwarded-host") or request.headers.get("host")
        # Prefer the explicit forwarded proto (reverse proxies set it). Fall
        # back to the actual connection scheme so local dev over plain HTTP
        # advertises http:// instead of a hardcoded https:// that won't match
        # what OAuth clients actually connect to.
        forwarded_proto = request.headers.get(
            "x-forwarded-proto",
            request.url.scheme or "https",
        )
        if forwarded_host and forwarded_host not in ("glow-api:8000", "glow-api", "nginx:80", "nginx"):
            return f"{forwarded_proto}://{forwarded_host}"
    return ORIGIN


def oauth_401(request: Request | None = None) -> Response:
    """Return 401 with WWW-Authenticate header per RFC 9728."""
    base = _get_base_url(request)
    resource = f"{base}{APP_PREFIX}/mcp"
    prm_endpoint = f"{base}{APP_PREFIX}/.well-known/oauth-protected-resource"
    auth_endpoint = f"{KEYCLOAK_ISSUER}/protocol/openid-connect/auth"
    return Response(
        status_code=status.HTTP_401_UNAUTHORIZED,
        headers={
            "WWW-Authenticate": (
                f'Bearer realm="mcp", resource="{resource}", '
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
            base = _get_base_url(request)
            return JSONResponse(
                {
                    "resource": f"{base}{APP_PREFIX}/mcp",
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

        # Rewrite bare /mcp (no trailing slash) → /mcp/ so the Streamable-HTTP
        # mount matches. Clients following the PRM's `resource` URL land on
        # /mcp without a slash, and FastAPI's mount doesn't match that path.
        # Beta's nginx rewrites this at the proxy; locally nginx isn't in the
        # path, so normalize at the app level too. Defense in depth.
        if path == mcp_path or path == "/mcp":
            slashed = f"{mcp_path}/"
            request.scope["path"] = slashed
            request.scope["raw_path"] = slashed.encode()

        # Feature flag
        if not is_mcp_enabled():
            return JSONResponse(
                {"error": "mcp_disabled", "message": "MCP is currently disabled."},
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                headers={"Retry-After": "300"},
            )

        # --- Bearer token verification ---

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
            return oauth_401(request)

        # --- Keycloak OAuth verification ---

        try:
            # Offload to a worker thread: verify_jwt is synchronous and its
            # JWKS fetch (_get_jwks) does a blocking `requests.get` to
            # Keycloak. Calling it inline in this async middleware would freeze
            # the event loop on a slow Keycloak. Verification logic unchanged.
            claims = await asyncio.to_thread(verify_jwt, token)
            logger.debug(
                f"MCP OAuth token validated: "
                f"sub={claims.get('sub')}, azp={claims.get('azp')}"
            )
        except ValueError as e:
            logger.warning(
                f"MCP OAuth token validation failed: {e} | "
                f"token_shape={_token_shape(token)}"
            )
            return oauth_401(request)

        # --- Profile resolution (reuses resolve_identity._resolve_profile_id) ---

        from app.infra.globals import get_pool

        # Token for the profile_id ContextVar set below. Reset in the finally
        # around call_next so this MCP caller's profile_id never leaks forward
        # into the NEXT request on the same worker task. (Mirrors the
        # try/finally + ContextVar.reset(token) pattern in
        # server_timing.ServerTimingMiddleware.) Without this reset the value
        # set by this outer BaseHTTPMiddleware dispatch propagates across
        # requests under Starlette 0.47.3 — the inner DBLogging reset runs in a
        # child context that doesn't propagate back here — letting a subsequent
        # request read (and be authorized as) this caller's profile via the
        # MCP discovery path (_current_profile_id) or the dispatch fallback
        # (resolve_mcp_profile_id's profile_id_context.get).
        profile_token: Any | None = None

        pool = get_pool()
        if pool:
            try:
                profile_id = await _resolve_profile_id(claims, pool)
                if profile_id:
                    request.state.profile_id = str(profile_id)
                    from app.utils.logging.db_logger import set_profile_id

                    profile_token = set_profile_id(str(profile_id))
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

        try:
            return await call_next(request)
        finally:
            if profile_token is not None:
                from app.utils.logging.db_logger import profile_id_context

                profile_id_context.reset(profile_token)
