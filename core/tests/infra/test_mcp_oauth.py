from __future__ import annotations

from uuid import UUID

import pytest
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient
from starlette.requests import Request

from app.infra.mcp import oauth

# Patches target the source module since oauth.py uses lazy imports
_RESOLVE = "app.infra.identity.resolve_identity"


def test_oauth_401_points_clients_to_mcp_resource_metadata():
    response = oauth.oauth_401()

    assert response.status_code == 401
    header = response.headers["WWW-Authenticate"]
    assert 'resource="' in header
    assert 'resource_metadata="' in header
    assert 'authorization_uri="' in header
    assert 'scope="mcp-resource"' in header


@pytest.mark.asyncio
async def test_mcp_oauth_middleware_handles_metadata_and_auth_paths(monkeypatch):
    app = FastAPI()
    app.add_middleware(oauth.McpOAuthMiddleware)

    @app.api_route("/mcp", methods=["GET", "POST"])
    async def mcp_endpoint(request: Request):
        return {
            "profile_id": getattr(request.state, "profile_id", None),
        }

    transport = ASGITransport(app=app)

    async with AsyncClient(transport=transport, base_url="http://testserver") as client:
        auth_meta = await client.get("/.well-known/oauth-authorization-server")
        assert auth_meta.status_code == 200
        assert auth_meta.json()["issuer"] == oauth.KEYCLOAK_ISSUER

        prm = await client.get("/.well-known/oauth-protected-resource")
        assert prm.status_code == 200
        assert prm.json()["resource"] == oauth.MCP_RESOURCE

        missing = await client.get("/mcp")
        assert missing.status_code == 401

        monkeypatch.setattr(oauth, "is_mcp_enabled", lambda: False)
        disabled = await client.get("/mcp", headers={"Authorization": "Bearer token"})
        assert disabled.status_code == 503


@pytest.mark.asyncio
async def test_mcp_oauth_middleware_rewrites_sse_and_messages_paths(monkeypatch):
    app = FastAPI()
    app.add_middleware(oauth.McpOAuthMiddleware)

    @app.api_route("/mcp", methods=["GET", "POST"])
    async def mcp_endpoint(request: Request):
        return {"path": request.scope["path"]}

    monkeypatch.setattr(oauth, "is_mcp_enabled", lambda: True)
    monkeypatch.setattr(
        f"{_RESOLVE}.verify_jwt", lambda token: {"sub": "subject-1"}
    )

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://testserver") as client:
        sse = await client.get(
            "/mcp/sse/", headers={"Authorization": "Bearer token-123"}
        )
        messages = await client.post(
            "/mcp/messages", headers={"Authorization": "Bearer token-123"}
        )

    assert sse.status_code == 200
    assert sse.json()["path"] == "/mcp"
    assert messages.status_code == 200
    assert messages.json()["path"] == "/mcp"


@pytest.mark.asyncio
async def test_mcp_oauth_middleware_returns_401_on_invalid_token(monkeypatch):
    app = FastAPI()
    app.add_middleware(oauth.McpOAuthMiddleware)

    @app.get("/mcp")
    async def mcp_endpoint():
        return {"ok": True}

    monkeypatch.setattr(oauth, "is_mcp_enabled", lambda: True)
    monkeypatch.setattr(
        f"{_RESOLVE}.verify_jwt",
        lambda token: (_ for _ in ()).throw(ValueError("bad token")),
    )

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://testserver") as client:
        response = await client.get(
            "/mcp", headers={"Authorization": "Bearer token-123"}
        )

    assert response.status_code == 401


@pytest.mark.asyncio
async def test_mcp_oauth_middleware_attaches_profile_context(monkeypatch):
    app = FastAPI()
    app.add_middleware(oauth.McpOAuthMiddleware)

    @app.get("/mcp")
    async def mcp_endpoint(request: Request):
        return {
            "profile_id": request.state.profile_id,
        }

    async def fake_resolve_profile_id(claims, pool):
        return UUID("019b3be4-36f0-788c-9df2-481eb5917940")

    monkeypatch.setattr(oauth, "is_mcp_enabled", lambda: True)
    monkeypatch.setattr(
        f"{_RESOLVE}.verify_jwt",
        lambda token: {"sub": "subject-1", "email": "user@example.com"},
    )
    monkeypatch.setattr(
        f"{_RESOLVE}._resolve_profile_id", fake_resolve_profile_id
    )
    monkeypatch.setattr("app.infra.globals.get_pool", lambda: "fake-pool")
    monkeypatch.setattr(
        "app.utils.logging.db_logger.set_profile_id", lambda profile_id: None
    )

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://testserver") as client:
        response = await client.get(
            "/mcp", headers={"Authorization": "Bearer token-123"}
        )

    assert response.status_code == 200
    assert response.json() == {
        "profile_id": "019b3be4-36f0-788c-9df2-481eb5917940",
    }
