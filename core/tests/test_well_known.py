"""Tests for the RFC 8414 well-known metadata endpoint."""

from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.routes.well_known import oauth_authorization_server_metadata, router


def test_oauth_authorization_server_metadata_uses_environment_defaults(monkeypatch):
    monkeypatch.delenv("ORIGIN", raising=False)
    monkeypatch.delenv("APP_PREFIX", raising=False)
    monkeypatch.delenv("KEYCLOAK_REALM", raising=False)

    payload = oauth_authorization_server_metadata()

    assert payload["issuer"] == "http://localhost/auth/realms/master"
    assert payload["authorization_endpoint"].endswith("/protocol/openid-connect/auth")
    assert "mcp-resource" in payload["scopes_supported"]


def test_oauth_authorization_server_metadata_route_returns_current_contract(
    monkeypatch,
):
    monkeypatch.setenv("ORIGIN", "https://glow.example.com")
    monkeypatch.setenv("APP_PREFIX", "/api")
    monkeypatch.setenv("KEYCLOAK_REALM", "glow")

    app = FastAPI()
    app.include_router(router)

    with TestClient(app) as client:
        response = client.get("/.well-known/oauth-authorization-server")

    assert response.status_code == 200
    payload = response.json()
    assert payload["issuer"] == "https://glow.example.com/api/auth/realms/glow"
    assert payload["token_endpoint"].endswith("/protocol/openid-connect/token")
    assert payload["grant_types_supported"] == ["authorization_code"]
