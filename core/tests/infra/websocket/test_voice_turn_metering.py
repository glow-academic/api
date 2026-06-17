"""report-22 VOICE4: voice continuation turns must be metered (the first turn
is metered by /attempt/generate; in-session continuations were a no-op). The
run-complete audio branch meters the NEXT turn against the profile's
request_limit and trips a breaker (ends the session) when the quota is
exhausted — fail-open on any resolution error.
"""

from __future__ import annotations

from types import SimpleNamespace
from uuid import uuid4

import pytest
from fastapi import HTTPException

import app.infra.websocket.run_complete_impl as rci
from app.infra.websocket.run_complete_impl import _meter_audio_turn

pytestmark = pytest.mark.asyncio


def _profile(limit=10, interval="1 day"):
    return SimpleNamespace(request_limit=limit, request_limit_interval=interval)


def _wire(monkeypatch, *, profile, enforce):
    async def fake_resolve(pool, pid, redis):
        return profile

    monkeypatch.setattr(
        "app.infra.profile_identity_context.resolve_profile_identity_context",
        fake_resolve,
    )
    monkeypatch.setattr(
        "app.infra.identity.request_limit.enforce_request_limit", enforce
    )
    monkeypatch.setattr(rci, "_meter_audio_turn", _meter_audio_turn)  # use real
    # get_pool is called but unused by the fakes.
    monkeypatch.setattr("app.infra.globals.get_pool", lambda: object())


async def test_allows_when_under_limit(monkeypatch):
    called = {}

    async def enforce(redis, **kw):
        called.update(kw)  # under limit → no raise

    _wire(monkeypatch, profile=_profile(), enforce=enforce)
    sess = SimpleNamespace(profile_id=str(uuid4()))
    assert await _meter_audio_turn(sess, redis=object()) is True
    # Metered under the same operation as the first /generate turn.
    assert called["operation"] == "generate"
    assert called["request_limit"] == 10


async def test_trips_breaker_on_429(monkeypatch):
    async def enforce(redis, **kw):
        raise HTTPException(status_code=429, detail="rate limited")

    _wire(monkeypatch, profile=_profile(), enforce=enforce)
    sess = SimpleNamespace(profile_id=str(uuid4()))
    # 429 → breaker (False).
    assert await _meter_audio_turn(sess, redis=object()) is False


async def test_non_429_http_error_does_not_kill_call(monkeypatch):
    async def enforce(redis, **kw):
        raise HTTPException(status_code=500, detail="boom")

    _wire(monkeypatch, profile=_profile(), enforce=enforce)
    sess = SimpleNamespace(profile_id=str(uuid4()))
    assert await _meter_audio_turn(sess, redis=object()) is True  # fail-open


async def test_fail_open_when_no_profile_id():
    sess = SimpleNamespace(profile_id=None)
    assert await _meter_audio_turn(sess, redis=object()) is True


async def test_fail_open_on_resolve_error(monkeypatch):
    async def boom_resolve(pool, pid, redis):
        raise RuntimeError("db down")

    monkeypatch.setattr(
        "app.infra.profile_identity_context.resolve_profile_identity_context",
        boom_resolve,
    )
    monkeypatch.setattr("app.infra.globals.get_pool", lambda: object())
    sess = SimpleNamespace(profile_id=str(uuid4()))
    assert await _meter_audio_turn(sess, redis=object()) is True
