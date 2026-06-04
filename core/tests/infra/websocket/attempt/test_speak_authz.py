"""Regression test for #149 — attempt.chat_speak must gate identity + ownership.

The WS handler ``attempt_chat_speak`` pushes client-supplied PCM16 audio into a
live ``AudioSession.inbound_queue``. Pre-fix it called neither
``resolve_socket_identity`` (AUTHN) nor any ownership check (AUTHZ), so any
connected client could inject audio into ANY user's live voice session by
supplying its ``conversation_id``/``chat_id`` (cross-user IDOR + queue DoS).

Every sibling realtime handler gates on ``resolve_socket_identity(sid)``; speak
was the lone outlier. The fix adds the identity guard AND an owner-only check:
``str(identity.profile_id) == session.profile_id``.

Pure handler-layer unit tests: ``resolve_socket_identity`` and the in-memory
session lookups are monkeypatched, so no DB/Redis is required. The two blocked
tests FAIL on the pre-fix code (audio still enqueued) and PASS after; the
allowed (owner) test passes both ways.
"""

from __future__ import annotations

from uuid import UUID, uuid4

import pytest

from app.infra.identity.resolve_identity import Identity
from app.infra.websocket.session_store import AudioSession

import app.ws.attempt.speak as speak_mod

pytestmark = pytest.mark.asyncio

AUDIO_B = b"\x00\x01\x02\x03"


def _make_identity(profile_id: UUID) -> Identity:
    return Identity(
        profile_id=profile_id,
        session_id=uuid4(),
        email="t@example.com",
        role="member",
    )


def _make_session(profile_id: str) -> AudioSession:
    """Live session owned by ``profile_id`` (stored as str, per audio.py)."""
    return AudioSession(
        sid="owner-sid",
        chat_id="chat-1",
        run_id="run-1",
        group_id="group-1",
        conversation_id="conv-1",
        profile_id=profile_id,
    )


def _patch(
    monkeypatch: pytest.MonkeyPatch,
    *,
    identity: Identity | None,
    session: AudioSession,
) -> None:
    async def fake_resolve(sid: str) -> Identity | None:
        return identity

    monkeypatch.setattr(speak_mod, "resolve_socket_identity", fake_resolve)
    monkeypatch.setattr(
        speak_mod, "get_session_by_conversation_id", lambda cid: session
    )
    monkeypatch.setattr(speak_mod, "get_session_by_chat_id", lambda cid: session)


async def test_speak_blocked_without_identity(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """No stored socket identity → audio is NOT enqueued (#149 AUTHN gate)."""
    owner = uuid4()
    session = _make_session(str(owner))
    _patch(monkeypatch, identity=None, session=session)

    await speak_mod.attempt_chat_speak(
        "attacker-sid", {"conversation_id": "conv-1", "audio": AUDIO_B}
    )

    assert session.inbound_queue.empty(), "unauthenticated speak was enqueued (IDOR)"


async def test_speak_blocked_for_wrong_owner(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Identity = profile A, session owned by profile B → NOT enqueued (#149)."""
    owner = uuid4()
    attacker = uuid4()
    assert owner != attacker
    session = _make_session(str(owner))
    _patch(monkeypatch, identity=_make_identity(attacker), session=session)

    await speak_mod.attempt_chat_speak(
        "attacker-sid", {"conversation_id": "conv-1", "audio": AUDIO_B}
    )

    assert session.inbound_queue.empty(), "cross-user speak was enqueued (IDOR)"


async def test_speak_allowed_for_owner(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Identity profile matches the session owner → audio IS enqueued."""
    owner = uuid4()
    session = _make_session(str(owner))
    _patch(monkeypatch, identity=_make_identity(owner), session=session)

    await speak_mod.attempt_chat_speak(
        "owner-sid", {"conversation_id": "conv-1", "audio": AUDIO_B}
    )

    assert not session.inbound_queue.empty(), "owner speak was dropped"
    msg = session.inbound_queue.get_nowait()
    assert msg["type"] == "audio"
    assert msg["pcm16_bytes"] == AUDIO_B
