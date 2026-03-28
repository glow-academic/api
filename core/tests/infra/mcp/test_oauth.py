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
        "app.infra.mcp.oauth.extract_bearer_token",
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
        "app.infra.mcp.oauth.extract_bearer_token",
        return_value="bad-token",
    ):
        with patch(
            "app.infra.mcp.oauth.verify_jwt",
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
