"""Regression test for #149 — attempt.chat_speak must gate identity + ownership.

The WS handler ``attempt_chat_speak`` pushes client-supplied PCM16 audio into a
live ``AudioSession.inbound_queue``. Pre-fix it called neither
``resolve_socket_identity`` (AUTHN) nor any ownership check (AUTHZ), so any
connected client could inject audio into ANY user's live voice session by
supplying its ``conversation_id``/``chat_id`` (cross-user IDOR + queue DoS).

Every sibling realtime handler gates on ``resolve_socket_identity(sid)``; speak
was the lone outlier. The fix adds the identity guard AND an owner-only check:
``str(identity.profile_id) == session.profile_id``.

W1 (WS↔HTTP shared impl): the ownership guard now lives in the shared
``app.infra.attempt.speak.chat_speak_impl`` that BOTH the WS handler and the
HTTP route call, so the in-memory session lookups are monkeypatched on the
*impl* module (where they're imported), not on the WS handler. The WS handler
still owns the AUTHN ``resolve_socket_identity`` gate.

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

import app.infra.attempt.speak as impl_mod
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
    # Session lookups now live in the shared impl (W1); patch them there.
    monkeypatch.setattr(
        impl_mod, "get_session_by_conversation_id", lambda cid: session
    )
    monkeypatch.setattr(impl_mod, "get_session_by_chat_id", lambda cid: session)


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


# ─────────────────────────────────────────────────────────────────────────────
# W1: the HTTP twin (POST /attempt/chat_speak) must enforce the SAME owner guard
# via the shared chat_speak_impl. Pre-fix the inlined HTTP route only checked
# that *a* profile existed and enqueued by caller-supplied conversation_id with
# NO owner comparison (cross-user audio injection).
# ─────────────────────────────────────────────────────────────────────────────

import base64

from fastapi import HTTPException

import app.routes.attempt.chat_speak as http_mod


class _State:
    def __init__(self, profile_id):
        self.profile_id = profile_id


class _Req:
    def __init__(self, profile_id):
        self.state = _State(profile_id)


def _patch_sessions(monkeypatch, session):
    monkeypatch.setattr(
        impl_mod, "get_session_by_conversation_id", lambda cid: session
    )
    monkeypatch.setattr(impl_mod, "get_session_by_chat_id", lambda cid: session)


def _http_body(audio_b64: str):
    return http_mod.ChatSpeakRequest(
        conversation_id=uuid4(), audio=audio_b64
    )


async def test_http_speak_blocked_for_wrong_owner(monkeypatch):
    """HTTP: caller profile A, session owned by B → 403, NO audio enqueued."""
    owner, attacker = uuid4(), uuid4()
    assert owner != attacker
    session = _make_session(str(owner))
    _patch_sessions(monkeypatch, session)

    with pytest.raises(HTTPException) as exc:
        await http_mod.chat_speak(
            _http_body(base64.b64encode(AUDIO_B).decode()), _Req(str(attacker))
        )
    assert exc.value.status_code == 403
    assert session.inbound_queue.empty(), "cross-user HTTP speak was enqueued (W1)"


async def test_http_speak_missing_profile_401(monkeypatch):
    """HTTP: no resolved profile → 401 (AUTHN)."""
    session = _make_session(str(uuid4()))
    _patch_sessions(monkeypatch, session)
    with pytest.raises(HTTPException) as exc:
        await http_mod.chat_speak(
            _http_body(base64.b64encode(AUDIO_B).decode()), _Req(None)
        )
    assert exc.value.status_code == 401


async def test_http_speak_allowed_for_owner(monkeypatch):
    """HTTP: caller owns the session → enqueued."""
    owner = uuid4()
    session = _make_session(str(owner))
    _patch_sessions(monkeypatch, session)

    resp = await http_mod.chat_speak(
        _http_body(base64.b64encode(AUDIO_B).decode()), _Req(str(owner))
    )
    assert resp.accepted is True
    assert not session.inbound_queue.empty()
    assert session.inbound_queue.get_nowait()["pcm16_bytes"] == AUDIO_B
