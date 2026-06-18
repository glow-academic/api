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


# ── run_complete_impl audio branch: first-turn guard (VOICE4-b) + canonical
#    breaker teardown (VOICE4-c) ────────────────────────────────────────────────


async def _drive_audio_complete(monkeypatch, *, session, meter_result=True):
    """Drive run_complete_impl's audio-continuation branch with fakes; return a
    record of what the branch did (meter calls, run rotations, cleanup calls)."""
    calls = {"meter": 0, "rotate": [], "cleanup": 0}

    monkeypatch.setattr(
        "app.infra.websocket.session_store.get_session_by_group_id",
        lambda gid: session,
    )

    def _rotate(sess, new_run_id):
        calls["rotate"].append(new_run_id)

    monkeypatch.setattr(
        "app.infra.websocket.session_store.rotate_run_id", _rotate
    )

    async def _meter(sess, redis):
        calls["meter"] += 1
        return meter_result

    monkeypatch.setattr(rci, "_meter_audio_turn", _meter)

    async def _cleanup(sess):
        calls["cleanup"] += 1

    monkeypatch.setattr(
        "app.infra.websocket.audio_lifecycle.cleanup_audio_session", _cleanup
    )

    async def _emit(*a, **k):
        pass

    await rci.run_complete_impl(
        {"modality": "audio", "group_id": "g", "run_id": "r0"},
        emit=_emit,
        conn=object(),
        redis=object(),
    )
    return calls


def _audio_session(*, first_seen):
    return SimpleNamespace(
        group_id="g",
        run_id="r0",
        profile_id=str(uuid4()),
        first_audio_turn_complete_seen=first_seen,
    )


async def test_first_audio_turn_not_metered_only_marked(monkeypatch):
    """VOICE4-b: the first run-complete is the turn /attempt/generate already
    metered — it must NOT meter again, only mark the session + rotate the run."""
    sess = _audio_session(first_seen=False)
    calls = await _drive_audio_complete(monkeypatch, session=sess)
    assert calls["meter"] == 0
    assert sess.first_audio_turn_complete_seen is True
    assert len(calls["rotate"]) == 1
    assert calls["cleanup"] == 0


async def test_continuation_turn_is_metered_and_rotates(monkeypatch):
    """VOICE4-b: a genuine continuation (flag already set) IS metered, and on
    success rotates into the next turn."""
    sess = _audio_session(first_seen=True)
    calls = await _drive_audio_complete(monkeypatch, session=sess, meter_result=True)
    assert calls["meter"] == 1
    assert len(calls["rotate"]) == 1
    assert calls["cleanup"] == 0


async def test_breaker_uses_canonical_cleanup_not_rotate(monkeypatch):
    """VOICE4-c: a continuation that hits the quota must tear down via
    cleanup_audio_session (which cancels the queue-blocked uplink/downlink tasks)
    and must NOT rotate into another free turn."""
    sess = _audio_session(first_seen=True)
    calls = await _drive_audio_complete(monkeypatch, session=sess, meter_result=False)
    assert calls["meter"] == 1
    assert calls["cleanup"] == 1
    assert calls["rotate"] == []
