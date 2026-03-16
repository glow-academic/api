from __future__ import annotations

from types import SimpleNamespace

import pytest
from jose import jwt

from app.infra.identity.default_idp import exchange_code_for_tokens, resolve_authorization


def test_exchange_code_for_tokens_puts_profile_identity_on_access_token():
    code = "code-access-token-contract"

    from app.infra.identity import default_idp

    default_idp._authorization_codes[code] = {
        "profile_id": "019ce726-fa14-7f2a-aebb-0067bca4b029",
        "email": "alice@example.com",
        "name": "Alice Example",
        "role": "admin",
        "nonce": "nonce-123",
        "expires_at": 4102444800,
        "client_id": "test-client",
        "redirect_uri": "http://localhost/callback",
        "is_emulation": True,
        "actor_profile_id": "019ce726-fa14-7f2a-aebb-0067bca4b030",
    }

    tokens = exchange_code_for_tokens(
        grant_type="authorization_code",
        code=code,
        redirect_uri="http://localhost/callback",
        client_id="test-client",
    )

    access_claims = jwt.get_unverified_claims(tokens["access_token"])
    id_claims = jwt.get_unverified_claims(tokens["id_token"])

    assert access_claims["profile_id"] == "019ce726-fa14-7f2a-aebb-0067bca4b029"
    assert access_claims["role"] == "admin"
    assert access_claims["is_emulation"] is True
    assert (
        access_claims["actor_profile_id"] == "019ce726-fa14-7f2a-aebb-0067bca4b030"
    )

    assert access_claims["profile_id"] == id_claims["profile_id"]
    assert access_claims["role"] == id_claims["role"]
    assert access_claims["is_emulation"] == id_claims["is_emulation"]
    assert access_claims["actor_profile_id"] == id_claims["actor_profile_id"]


@pytest.mark.asyncio
async def test_resolve_authorization_uses_profile_identity_context_for_email(monkeypatch):
    from app.infra.identity import default_idp

    async def fake_resolve_profile_identity_context(
        pool,
        profile_id,
        redis,
        bypass_cache=False,
    ):
        return SimpleNamespace(
            primary_email="artifact-email@example.com",
            name="Artifact User",
            role="admin",
        )

    monkeypatch.setattr(
        default_idp,
        "resolve_profile_identity_context",
        fake_resolve_profile_identity_context,
    )

    redirect = await resolve_authorization(
        pool=object(),
        redis=object(),
        response_type="code",
        client_id="test-client",
        redirect_uri="http://localhost/callback",
        state="state-123",
        nonce="nonce-123",
        profile_id=default_idp.UUID("019ce726-fa14-7f2a-aebb-0067bca4b029"),
        emulation_grant=None,
        login_hint=None,
    )

    assert redirect.startswith("http://localhost/callback?code=")


@pytest.mark.asyncio
async def test_resolve_authorization_falls_back_to_first_linked_email(monkeypatch):
    from app.infra.identity import default_idp

    async def fake_resolve_profile_identity_context(
        pool,
        profile_id,
        redis,
        bypass_cache=False,
    ):
        return SimpleNamespace(
            primary_email=None,
            emails=["fallback@example.com", "other@example.com"],
            name="Fallback User",
            role="admin",
        )

    monkeypatch.setattr(
        default_idp,
        "resolve_profile_identity_context",
        fake_resolve_profile_identity_context,
    )

    redirect = await resolve_authorization(
        pool=object(),
        redis=object(),
        response_type="code",
        client_id="test-client",
        redirect_uri="http://localhost/callback",
        state="state-123",
        nonce="nonce-123",
        profile_id=default_idp.UUID("019ce726-fa14-7f2a-aebb-0067bca4b029"),
        emulation_grant=None,
        login_hint=None,
    )

    code = redirect.split("code=")[1].split("&", 1)[0]
    assert default_idp._authorization_codes[code]["email"] == "fallback@example.com"
