"""OAuth middleware for MCP server — Keycloak integration.

Handles:
  - OAuth discovery endpoints (RFC 8414, RFC 9728)
  - Bearer token verification (delegates to resolve_identity.verify_jwt)
  - LearnLoop-signed MCP proxy token verification (for external MCP access)
  - Profile resolution from JWT claims (delegates to resolve_identity._resolve_profile_id)
  - Feature flag gating (is_mcp_enabled)
  - Path rewriting for Cursor/ChatGPT compatibility
"""

import logging
import os
import time
from typing import Any

import httpx
from jose import jwt

from fastapi import Request, Response, status
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware

logger = logging.getLogger(__name__)

# Configuration from environment
ORIGIN = os.getenv("ORIGIN", "http://localhost")
APP_PREFIX = os.getenv("APP_PREFIX", "")
KEYCLOAK_REALM = os.getenv("KEYCLOAK_REALM", "master")

# LearnLoop proxy token configuration
LEARNLOOP_API_URL = (os.getenv("LEARNLOOP_API_URL", "").rstrip("/") or None)
DEPLOYMENT_ID = (
    os.getenv("DEPLOYMENT_ID")
    or os.getenv("COMPOSE_PROJECT_NAME")
    or None
)

# LearnLoop JWKS cache (1 hour TTL)
_learnloop_jwks_cache: dict[str, Any] = {"keys": None, "ts": 0.0}
_LEARNLOOP_JWKS_TTL = 3600  # 1 hour


async def _get_learnloop_jwks() -> list[dict[str, Any]]:
    """Fetch JWKS from LearnLoop API with 1-hour caching."""
    now = time.time()
    if (
        _learnloop_jwks_cache["keys"] is not None
        and now - _learnloop_jwks_cache["ts"] <= _LEARNLOOP_JWKS_TTL
    ):
        return _learnloop_jwks_cache["keys"]

    jwks_url = f"{LEARNLOOP_API_URL}/jwks"
    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            resp = await client.get(jwks_url)
            resp.raise_for_status()
            keys = resp.json().get("keys", [])
            if keys:
                _learnloop_jwks_cache["keys"] = keys
                _learnloop_jwks_cache["ts"] = now
                logger.debug(
                    f"Fetched {len(keys)} keys from LearnLoop JWKS"
                )
                return keys
    except Exception as e:
        logger.warning(f"Failed to fetch LearnLoop JWKS from {jwks_url}: {e}")

    # Fall back to cached keys if available
    if _learnloop_jwks_cache["keys"] is not None:
        logger.warning("Failed to refresh LearnLoop JWKS, using cached keys")
        return _learnloop_jwks_cache["keys"]

    raise RuntimeError(f"Failed to fetch LearnLoop JWKS from {jwks_url}")


async def _verify_learnloop_proxy_token(
    token: str,
) -> dict[str, Any] | None:
    """Verify a LearnLoop-signed MCP proxy token.

    Returns the claims dict if valid, or None if the token is not a
    LearnLoop proxy token (so the caller should fall through to Keycloak).

    Raises ValueError if the token IS a LearnLoop proxy token but is invalid.
    """
    if not LEARNLOOP_API_URL or not DEPLOYMENT_ID:
        return None

    # Peek at claims without verification to check issuer + type
    try:
        unverified = jwt.get_unverified_claims(token)
    except Exception:
        return None

    # Only handle tokens issued by LearnLoop with type=mcp_proxy
    if unverified.get("iss") != LEARNLOOP_API_URL:
        return None
    if unverified.get("type") != "mcp_proxy":
        return None

    # This IS a LearnLoop proxy token — now verify it strictly
    try:
        headers = jwt.get_unverified_header(token)
        kid = headers.get("kid")
        if not kid:
            raise ValueError("LearnLoop proxy token missing kid header")

        keys = await _get_learnloop_jwks()
        key = next((k for k in keys if k.get("kid") == kid), None)
        if not key:
            raise ValueError(
                f"No matching LearnLoop JWK for kid={kid}"
            )

        claims = jwt.decode(
            token,
            key,
            algorithms=[headers.get("alg", "RS256")],
            options={
                "verify_aud": False,
                "verify_at_hash": False,
            },
            issuer=LEARNLOOP_API_URL,
        )

        # Verify deployment_id matches this instance
        token_deployment_id = claims.get("deployment_id")
        if token_deployment_id != DEPLOYMENT_ID:
            raise ValueError(
                f"deployment_id mismatch: token has {token_deployment_id!r}, "
                f"expected {DEPLOYMENT_ID!r}"
            )

        return claims

    except ValueError:
        raise
    except jwt.ExpiredSignatureError as e:
        raise ValueError("LearnLoop proxy token expired") from e
    except jwt.JWTClaimsError as e:
        raise ValueError(
            f"LearnLoop proxy token claims invalid: {e}"
        ) from e
    except Exception as e:
        raise ValueError(
            f"LearnLoop proxy token verification failed: {e}"
        ) from e


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


def _get_base_url(request: Request | None = None) -> str:
    """Get the base URL from the request's forwarded host, falling back to ORIGIN.

    This allows MCP endpoints to work when accessed through different domains
    (e.g., docs domain proxying to the API). The OAuth discovery URLs will
    match the domain the client actually connected to.
    """
    if request:
        forwarded_host = request.headers.get("x-forwarded-host") or request.headers.get("host")
        forwarded_proto = request.headers.get("x-forwarded-proto", "https")
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

        if not path.startswith(mcp_path) and not path.startswith("/mcp") and not path.startswith("/docs-mcp"):
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

        # --- Try LearnLoop-signed MCP proxy token first ---

        is_learnloop_proxy = False
        try:
            proxy_claims = await _verify_learnloop_proxy_token(token)
            if proxy_claims is not None:
                # Valid LearnLoop proxy token — treat as authenticated
                # external user (no Glow profile required)
                is_learnloop_proxy = True
                claims = proxy_claims
                request.state.mcp_proxy = True
                request.state.mcp_proxy_sub = claims.get("sub", "")
                request.state.mcp_proxy_name = claims.get("name", "")
                logger.info(
                    f"MCP LearnLoop proxy token accepted: "
                    f"sub={claims.get('sub')}, name={claims.get('name')}, "
                    f"deployment_id={claims.get('deployment_id')}"
                )
        except ValueError as e:
            # Token IS a LearnLoop proxy token but failed verification
            logger.warning(f"MCP LearnLoop proxy token rejected: {e}")
            return oauth_401(request)

        # --- Fall through to Keycloak OAuth verification ---

        if not is_learnloop_proxy:
            try:
                claims = verify_jwt(token)
                logger.debug(
                    f"MCP OAuth token validated: "
                    f"sub={claims.get('sub')}, azp={claims.get('azp')}"
                )
            except ValueError as e:
                logger.warning(f"MCP OAuth token validation failed: {e}")
                return oauth_401(request)

        # --- Profile resolution (reuses resolve_identity._resolve_profile_id) ---
        # Skip profile resolution for LearnLoop proxy tokens — they don't
        # need a local Glow profile.

        if not is_learnloop_proxy:
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
