"""Tests for MCP OAuth middleware — discovery endpoints and auth gating."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi import status

from app.infra.mcp.oauth import (
    KEYCLOAK_ISSUER,
    MCP_RESOURCE,
    McpOAuthMiddleware,
    is_mcp_enabled,
    oauth_401,
)

pytestmark = pytest.mark.asyncio


def _make_request(path: str, method: str = "GET", auth_header: str | None = None):
    """Create a mock Starlette Request for middleware tests."""
    headers = {}
    if auth_header:
        headers["authorization"] = auth_header

    request = MagicMock()
    request.url.path = path
    request.method = method
    request.headers = MagicMock()
    request.headers.get = lambda key, default=None: headers.get(key, default)
    request.scope = {
        "type": "http",
        "method": method,
        "path": path,
        "headers": [],
    }
    request.state = MagicMock()
    return request


async def test_is_mcp_enabled_returns_true():
    """MCP is enabled by default."""
    assert is_mcp_enabled() is True


async def test_oauth_401_has_www_authenticate_header():
    """oauth_401 returns 401 with proper WWW-Authenticate header."""
    response = oauth_401()

    assert response.status_code == status.HTTP_401_UNAUTHORIZED
    www_auth = response.headers.get("WWW-Authenticate", "")
    assert "Bearer" in www_auth
    assert "realm" in www_auth
    assert "mcp" in www_auth


async def test_middleware_passes_options_through():
    """OPTIONS (CORS preflight) requests pass through without auth."""
    middleware = McpOAuthMiddleware(app=MagicMock())
    request = _make_request("/mcp", method="OPTIONS")

    call_next = AsyncMock(return_value=MagicMock(status_code=200))
    response = await middleware.dispatch(request, call_next)

    call_next.assert_called_once_with(request)


async def test_middleware_serves_oauth_authorization_server_discovery():
    """The /.well-known/oauth-authorization-server endpoint returns discovery JSON."""
    middleware = McpOAuthMiddleware(app=MagicMock())
    request = _make_request("/.well-known/oauth-authorization-server")

    call_next = AsyncMock()
    response = await middleware.dispatch(request, call_next)

    assert response.status_code == 200
    body = response.body.decode()
    assert "issuer" in body
    assert "authorization_endpoint" in body
    assert "token_endpoint" in body
    assert "scopes_supported" in body


async def test_middleware_serves_prm_discovery():
    """The /.well-known/oauth-protected-resource endpoint returns PRM JSON."""
    middleware = McpOAuthMiddleware(app=MagicMock())
    request = _make_request("/.well-known/oauth-protected-resource")

    call_next = AsyncMock()
    response = await middleware.dispatch(request, call_next)

    assert response.status_code == 200
    body = response.body.decode()
    assert "resource" in body
    assert "authorization_servers" in body
    assert "S256" in body


async def test_middleware_returns_401_for_mcp_without_token():
    """MCP requests without Authorization header get 401."""
    middleware = McpOAuthMiddleware(app=MagicMock())
    request = _make_request("/mcp")

    call_next = AsyncMock()

    with patch(
        "app.infra.identity.resolve_identity.extract_bearer_token",
        return_value=None,
    ):
        response = await middleware.dispatch(request, call_next)

    assert response.status_code == 401


async def test_middleware_returns_401_for_invalid_token():
    """MCP requests with an invalid JWT get 401."""
    middleware = McpOAuthMiddleware(app=MagicMock())
    request = _make_request("/mcp", auth_header="Bearer bad-token")

    call_next = AsyncMock()

    with patch(
        "app.infra.identity.resolve_identity.extract_bearer_token",
        return_value="bad-token",
    ):
        with patch(
            "app.infra.identity.resolve_identity.verify_jwt",
            side_effect=ValueError("invalid"),
        ):
            response = await middleware.dispatch(request, call_next)

    assert response.status_code == 401


async def test_middleware_passes_non_mcp_paths_through():
    """Non-MCP paths (not /mcp or discovery) pass through to the app."""
    middleware = McpOAuthMiddleware(app=MagicMock())
    request = _make_request("/api/health")

    call_next = AsyncMock(return_value=MagicMock(status_code=200))
    response = await middleware.dispatch(request, call_next)

    call_next.assert_called_once_with(request)


async def test_middleware_resets_profile_id_contextvar_after_request() -> None:
    """X1 regression: an MCP request must NOT leak its profile_id into the
    next request on the same worker task.

    Two sequential dispatches share one task (one ContextVar context, as a
    real Starlette worker task does). Request 1 authenticates as profile A and
    sets profile_id_context. Without the per-request reset, the value survives
    past call_next and request 2 — which never authenticates — would read A
    via the MCP discovery path (_current_profile_id) and the dispatch fallback
    (resolve_mcp_profile_id). With the try/finally + ContextVar.reset(token)
    the var is restored to its prior (None) state after request 1.
    """
    from app.utils.logging.db_logger import profile_id_context

    profile_a = "11111111-1111-1111-1111-111111111111"

    # Baseline: nothing set on this task before any request runs.
    token = profile_id_context.set(None)
    try:
        assert profile_id_context.get(None) is None

        middleware = McpOAuthMiddleware(app=MagicMock())

        # --- Request 1: an authenticated MCP request for profile A ---
        req1 = _make_request("/mcp", auth_header="Bearer good-token")
        call_next_1 = AsyncMock(return_value=MagicMock(status_code=200))

        with patch(
            "app.infra.identity.resolve_identity.extract_bearer_token",
            return_value="good-token",
        ), patch(
            "app.infra.identity.resolve_identity.verify_jwt",
            return_value={"sub": "a", "email": "a@example.com"},
        ), patch(
            "app.infra.globals.get_pool",
            return_value=MagicMock(),
        ), patch(
            "app.infra.identity.resolve_identity._resolve_profile_id",
            new=AsyncMock(return_value=profile_a),
        ):
            await middleware.dispatch(req1, call_next_1)

            # Inside the request the profile is set (discovery/dispatch read it).
            assert call_next_1.await_count == 1

        # --- The leak assertion: after request 1 returns, the var is reset ---
        # If the reset were missing, this would read profile_a and request 2
        # below would authorize as A.
        assert profile_id_context.get(None) is None, (
            "MCP profile_id leaked past the request boundary"
        )

        # --- Request 2: a request that never authenticates via MCP ---
        # It must not observe request 1's profile_id.
        req2 = _make_request("/api/health")
        call_next_2 = AsyncMock(return_value=MagicMock(status_code=200))
        await middleware.dispatch(req2, call_next_2)

        assert profile_id_context.get(None) is None, (
            "request 2 saw the previous MCP caller's profile_id"
        )
    finally:
        profile_id_context.reset(token)
