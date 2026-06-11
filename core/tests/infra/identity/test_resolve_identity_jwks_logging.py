"""O2 — JWKS fetch-failure observability.

`_get_jwks` fetches Keycloak's public keys to verify auth tokens. When that
fetch fails the auth subsystem is degrading (Keycloak unreachable / key
rotation in flight), but the per-endpoint failure used to be logged at `debug`
— invisible to operators. These tests assert the FAILURE path now logs at
WARNING (and includes the endpoint), while leaving routine success at debug.

Deps mocked only at the boundary (the blocking `requests.get` and the
default-idp key source); the cache + control flow are exercised for real.
"""

from __future__ import annotations

import logging

import pytest

import app.infra.identity.resolve_identity as ri

_LOGGER = "app.infra.identity.resolve_identity"


@pytest.fixture(autouse=True)
def _reset_jwks_state(monkeypatch):
    # Force a cold cache so every test takes the real fetch path, and make the
    # keycloak hostname "resolvable" so no endpoint is skipped.
    monkeypatch.setattr(ri, "_jwks_cache", {"keys": None, "ts": 0.0, "url": None})
    monkeypatch.setattr(ri, "_can_resolve_hostname", lambda host: True)
    yield


def _raising_get(exc):
    def _get(url, timeout=None):
        raise exc
    return _get


def test_jwks_fetch_failure_logs_warning_with_url(monkeypatch, caplog):
    """A per-endpoint fetch failure must log at WARNING and name the URL —
    previously this was a context-light debug line."""
    monkeypatch.setattr(
        ri.requests, "get", _raising_get(ConnectionError("keycloak down"))
    )
    # default-idp provides a usable key so _get_jwks succeeds overall; we only
    # assert the per-endpoint failure was surfaced.
    monkeypatch.setattr(
        "app.infra.identity.jwks.get_jwks",
        lambda: {"keys": [{"kid": "default-1"}]},
    )

    with caplog.at_level(logging.DEBUG, logger=_LOGGER):
        keys = ri._get_jwks()

    assert keys == [{"kid": "default-1"}]
    fetch_warnings = [
        r for r in caplog.records
        if r.levelno == logging.WARNING and "JWKS fetch failed" in r.getMessage()
    ]
    assert fetch_warnings, "per-endpoint JWKS fetch failure must log at WARNING"
    # Endpoint + error class are attributable in the message.
    msg = fetch_warnings[0].getMessage()
    assert "ConnectionError" in msg


def test_jwks_total_failure_falls_back_to_cache_with_warning(monkeypatch, caplog):
    """When every endpoint fails but a cached key set exists, the fallback must
    warn (with context) that auth is running on stale keys."""
    monkeypatch.setattr(
        ri, "_jwks_cache", {"keys": [{"kid": "cached-1"}], "ts": 0.0, "url": None}
    )
    monkeypatch.setattr(
        ri.requests, "get", _raising_get(TimeoutError("slow keycloak"))
    )
    # default-idp also unavailable → forces the cached-fallback branch.
    monkeypatch.setattr(
        "app.infra.identity.jwks.get_jwks",
        lambda: (_ for _ in ()).throw(RuntimeError("no default idp")),
    )

    with caplog.at_level(logging.DEBUG, logger=_LOGGER):
        keys = ri._get_jwks()

    assert keys == [{"kid": "cached-1"}]
    fallback = [
        r for r in caplog.records
        if r.levelno == logging.WARNING
        and "falling back to cached keys" in r.getMessage()
    ]
    assert fallback, "cached-key fallback must log at WARNING"
    # default-idp loss is also surfaced at WARNING (not debug).
    default_idp = [
        r for r in caplog.records
        if r.levelno == logging.WARNING
        and "default-idp JWKS" in r.getMessage()
    ]
    assert default_idp, "default-idp JWKS load failure must log at WARNING"


def test_jwks_success_does_not_warn(monkeypatch, caplog):
    """Control: a clean fetch logs at debug only — no failure WARNING noise."""
    class _Resp:
        def raise_for_status(self):
            return None

        def json(self):
            return {"keys": [{"kid": "kc-1"}]}

    monkeypatch.setattr(ri.requests, "get", lambda url, timeout=None: _Resp())
    monkeypatch.setattr(
        "app.infra.identity.jwks.get_jwks", lambda: {"keys": []}
    )

    with caplog.at_level(logging.DEBUG, logger=_LOGGER):
        keys = ri._get_jwks()

    assert {"kid": "kc-1"} in keys
    assert not [
        r for r in caplog.records if r.levelno == logging.WARNING
    ], "a successful JWKS fetch must not emit WARNINGs"
