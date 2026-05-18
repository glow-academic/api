from __future__ import annotations

import pytest

from app.infra.identity import resolve_identity


def test_get_jwks_includes_builtin_default_idp_keys_when_remote_jwks_do_not_match(
    monkeypatch,
):
    resolve_identity._jwks_cache.update({"keys": None, "ts": 0.0, "url": None})

    class FakeResponse:
        def raise_for_status(self):
            return None

        def json(self):
            return {"keys": [{"kid": "remote-key"}]}

    monkeypatch.setattr(resolve_identity, "_can_resolve_hostname", lambda _: True)
    monkeypatch.setattr(
        resolve_identity.requests,
        "get",
        lambda url, timeout: FakeResponse(),
    )
    monkeypatch.setattr(
        "app.infra.identity.jwks.get_jwks",
        lambda: {"keys": [{"kid": "default-idp-key-1"}]},
    )

    keys = resolve_identity._get_jwks()

    assert [key["kid"] for key in keys] == ["remote-key", "default-idp-key-1"]


def test_verify_jwt_accepts_builtin_default_idp_tokens(monkeypatch):
    monkeypatch.setattr(
        resolve_identity.jwt,
        "get_unverified_header",
        lambda token: {"kid": "default-idp-key-1", "alg": "RS256"},
    )
    monkeypatch.setattr(
        resolve_identity,
        "_get_jwks",
        lambda: [{"kid": "default-idp-key-1"}],
    )
    monkeypatch.setattr(
        resolve_identity.jwt,
        "decode",
        lambda token, key, algorithms, options: {
            "iss": resolve_identity._default_idp_base,
            "profile_id": "019ce726-fa14-7f2a-aebb-0067bca4b029",
        },
    )

    claims = resolve_identity.verify_jwt("token-123")

    assert claims["profile_id"] == "019ce726-fa14-7f2a-aebb-0067bca4b029"
