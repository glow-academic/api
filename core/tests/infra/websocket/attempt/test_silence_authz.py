"""Regression test for R3 — attempt.chat_silence must gate session ownership.

``_perform_silence`` ends a LIVE voice session (DB completion + adapter cleanup
+ session_complete/voice_ended emits) resolved by a caller-supplied ``chat_id``.
Pre-fix it ran NO ownership check, so any authenticated user could tear down a
victim's live voice session by supplying its ``chat_id`` (ephemeral DoS).

This is the symmetric sibling of the W1 ``chat_speak_impl`` owner guard for the
same in-memory ``AudioSession`` keyed by the same ``chat_id``. The fix mirrors
it: only the authenticated owner (``str(profile_id) == session.profile_id``) may
silence; a non-owner (or a caller with no resolved profile) is denied with NO
teardown — no DB completion, no cleanup, no emit.

Pure handler/impl unit tests: the in-memory session lookup, DB-completion,
cleanup, and emit are all monkeypatched, so no DB/Redis is required. The blocked
tests assert NO teardown side effect ran; the owner test asserts it did.
"""

from __future__ import annotations

from uuid import uuid4

import pytest

import app.infra.websocket.attempt.chat.silence as silence_mod
import app.routes.attempt.chat_silence as http_mod
import app.ws.attempt.chat.silence as ws_mod
from app.infra.identity.resolve_identity import Identity
from app.infra.websocket.session_store import AudioSession

pytestmark = pytest.mark.asyncio


def _make_session(profile_id: str) -> AudioSession:
    """Live voice session owned by ``profile_id`` (stored as str, per audio.py)."""
    return AudioSession(
        sid="owner-sid",
        chat_id="chat-1",
        run_id="run-1",
        group_id="group-1",
        conversation_id=str(uuid4()),  # UUID-shaped: completion path parses it
        session_id=str(uuid4()),
        profile_id=profile_id,
    )


class _Spy:
    """Records whether the teardown side effects ran."""

    def __init__(self) -> None:
        self.cleaned = False
        self.emits = 0
        self.completed = False


def _patch(monkeypatch: pytest.MonkeyPatch, session: AudioSession | None) -> _Spy:
    spy = _Spy()

    monkeypatch.setattr(silence_mod, "get_session_by_chat_id", lambda cid: session)

    async def fake_cleanup(sess):
        spy.cleaned = True

    monkeypatch.setattr(silence_mod, "cleanup_audio_session", fake_cleanup)

    async def fake_completion(*a, **k):
        spy.completed = True

    monkeypatch.setattr(
        silence_mod, "create_attempt_conversation_completion", fake_completion
    )

    class _Sio:
        async def emit(self, *a, **k):
            spy.emits += 1

    monkeypatch.setattr(silence_mod, "get_internal_sio", lambda: _Sio())
    monkeypatch.setattr(silence_mod, "get_redis_client", lambda: object())

    class _Conn:
        async def __aenter__(self):
            return self

        async def __aexit__(self, *a):
            return False

    class _Pool:
        def acquire(self):
            return _Conn()

    monkeypatch.setattr(silence_mod, "get_pool", lambda: _Pool())
    return spy


async def test_silence_blocked_for_wrong_owner(monkeypatch):
    """Caller profile A, session owned by B → denied, NO teardown."""
    owner, attacker = uuid4(), uuid4()
    assert owner != attacker
    session = _make_session(str(owner))
    spy = _patch(monkeypatch, session)

    result = await silence_mod._perform_silence("chat-1", "attacker-sid", str(attacker))

    assert result.denied is True
    assert result.stopped is False
    assert not spy.cleaned, "victim's session was cleaned up (R3 IDOR)"
    assert not spy.completed, "victim's conversation was completed (R3 IDOR)"
    assert spy.emits == 0, "voice_ended/session_complete emitted for victim (R3 IDOR)"


async def test_silence_blocked_without_profile(monkeypatch):
    """No resolved caller profile → denied (can't prove ownership)."""
    session = _make_session(str(uuid4()))
    spy = _patch(monkeypatch, session)

    result = await silence_mod._perform_silence("chat-1", "sid", None)

    assert result.denied is True
    assert not spy.cleaned and not spy.completed and spy.emits == 0


async def test_silence_allowed_for_owner(monkeypatch):
    """Caller owns the session → teardown runs (cleanup + completion + emit)."""
    owner = uuid4()
    session = _make_session(str(owner))
    spy = _patch(monkeypatch, session)

    result = await silence_mod._perform_silence("chat-1", "owner-sid", str(owner))

    assert result.denied is False
    assert result.stopped is True
    assert spy.cleaned and spy.completed and spy.emits >= 1


async def test_silence_nonexistent_session_is_noop(monkeypatch):
    """No live session for the chat_id → benign no-op (not a denial)."""
    spy = _patch(monkeypatch, None)
    result = await silence_mod._perform_silence("chat-1", "sid", str(uuid4()))
    assert result.stopped is False and result.denied is False
    assert not spy.cleaned and not spy.completed and spy.emits == 0


# ─────────────────────────────────────────────────────────────────────────────
# HTTP edge: POST /attempt/chat_silence must surface a non-owner as 403.
# ─────────────────────────────────────────────────────────────────────────────


class _State:
    def __init__(self, profile_id, session_id):
        self.profile_id = profile_id
        self.session_id = session_id


class _Req:
    def __init__(self, profile_id, session_id=None):
        # session_id left None on purpose: the impl then takes the direct
        # ``_run()`` path (no audit wrapper / no group resolve), so the owner
        # guard inside ``_perform_silence`` is exercised without a DB.
        self.state = _State(profile_id, session_id)


async def test_http_silence_blocked_for_wrong_owner(monkeypatch):
    """HTTP: caller A, session owned by B → 403, NO teardown."""
    from fastapi import HTTPException

    owner, attacker = uuid4(), uuid4()
    session = _make_session(str(owner))
    spy = _patch(monkeypatch, session)

    body = http_mod.ChatSilenceRequest(chat_id=uuid4())
    with pytest.raises(HTTPException) as exc:
        await http_mod.chat_silence(body, _Req(str(attacker)))
    assert exc.value.status_code == 403
    assert not spy.cleaned and not spy.completed and spy.emits == 0


async def test_http_silence_missing_profile_401(monkeypatch):
    """HTTP: no resolved profile → 401 (AUTHN)."""
    from fastapi import HTTPException

    _patch(monkeypatch, _make_session(str(uuid4())))
    body = http_mod.ChatSilenceRequest(chat_id=uuid4())
    with pytest.raises(HTTPException) as exc:
        await http_mod.chat_silence(body, _Req(None))
    assert exc.value.status_code == 401


# ─────────────────────────────────────────────────────────────────────────────
# WS edge: the handler must thread the resolved profile_id into the impl so the
# owner guard can fire (pre-fix it passed only chat_id + sid).
# ─────────────────────────────────────────────────────────────────────────────


async def test_ws_silence_threads_profile_id(monkeypatch):
    """WS handler passes identity.profile_id into the impl (so the guard runs)."""
    profile = uuid4()

    async def fake_resolve(sid):
        return Identity(
            profile_id=profile,
            session_id=uuid4(),
            email="t@example.com",
            role="member",
        )

    captured: dict = {}

    async def fake_impl(data):
        captured.update(data)
        return silence_mod.AudioStopInternalResult(chat_id="chat-1", stopped=False)

    # Audit wrapper just runs the inner runner.
    async def fake_audit(*a, runner=None, **k):
        return await runner()

    monkeypatch.setattr(ws_mod, "resolve_socket_identity", fake_resolve)
    monkeypatch.setattr(ws_mod, "attempt_chat_silence_internal_impl", fake_impl)
    monkeypatch.setattr(ws_mod, "run_artifact_operation_with_audit", fake_audit)
    monkeypatch.setattr(ws_mod, "get_pool", lambda: object())
    monkeypatch.setattr(ws_mod, "get_redis_client", lambda: object())

    await ws_mod.attempt_chat_silence("a-sid", {"chat_id": "chat-1"})

    assert captured.get("profile_id") == str(profile), (
        "WS silence did not thread the caller profile into the owner guard (R3)"
    )
