"""Attempt chat_speak — shared audio-frame push primitive (WS + HTTP).

Pure in-memory data primitive: pushes/stages PCM16 audio bytes into a live
voice session's inbound queue. No DB, no AI. Sessions are keyed by the
client-facing ``conversation_id`` (or ``chat_id`` to resolve it) in
``session_store.py``.

WS↔HTTP shared impl (the durable W1 fix): the WS handler
(``ws/attempt/speak.py``) and the HTTP route (``routes/attempt/chat_speak.py``)
both funnel through :func:`chat_speak_impl` so the *session-ownership guard*
can never diverge between the two edges again. Closes the cross-user audio
injection gap (#149 was fixed on WS only; the inlined HTTP route re-opened it).

Ownership model (mirrors the WS #149 fix exactly): only the authenticated
owner of the live session may push audio into it. ``AudioSession.profile_id``
is stored as a ``str`` (audio.py sets ``profile_id=str(prepared.profile_id)``);
the caller's ``profile_id`` is the session-identity profile id (UUID), so we
compare stringified. This is intentionally *owner-only* — an instructor would
never legitimately speak into a student's live session, so there is no
super-admin / role-hierarchy bypass here (unlike the attempt READ/mutation
gates). Fail-closed: a missing/unknown session or a non-owner caller is denied
with NO side effect (no frame enqueued, no frame staged).
"""

from __future__ import annotations

import asyncio
import base64
import time
from dataclasses import dataclass
from uuid import UUID, uuid4

from app.infra.websocket.session_store import (
    AudioSession,
    get_session_by_chat_id,
    get_session_by_conversation_id,
)


@dataclass
class ChatSpeakResult:
    """Outcome of a chat_speak push/stage/ack.

    ``denied`` distinguishes an authorization failure (no session, or the
    caller does not own the session) from a benign ``accepted=False`` (e.g. a
    full inbound queue). The HTTP route maps ``denied`` to a 403/404; the WS
    handler simply returns (its contract is fire-and-forget).
    """

    accepted: bool
    idempotency_key: str | None = None
    denied: bool = False
    not_found: bool = False
    bad_audio: bool = False


def resolve_speak_session(
    conversation_id: UUID | str | None,
    chat_id: UUID | str | None,
) -> AudioSession | None:
    """Resolve the live AudioSession from a client-facing id (conversation or chat)."""
    if conversation_id:
        return get_session_by_conversation_id(str(conversation_id))
    if chat_id:
        return get_session_by_chat_id(str(chat_id))
    return None


def _enqueue(session: AudioSession, frame: bytes) -> bool:
    session.last_activity = time.monotonic()
    try:
        session.inbound_queue.put_nowait({"type": "audio", "pcm16_bytes": frame})
        return True
    except asyncio.QueueFull:
        return False


def chat_speak_impl(
    *,
    profile_id: UUID | str | None,
    conversation_id: UUID | str | None = None,
    chat_id: UUID | str | None = None,
    audio: bytes | str | None = None,
    soft: bool = False,
    accept: bool | None = None,
    idempotency_key: UUID | str | None = None,
) -> ChatSpeakResult:
    """Push (or stage / ack) an audio frame into a session, owner-guarded.

    Shared by the WS handler and the HTTP route so the ownership guard lives in
    exactly one place. Synchronous: the underlying queue ops are non-blocking
    (``put_nowait``) and the session store is an in-memory dict, so no DB / I/O
    happens here.

    Args:
        profile_id: the authenticated caller's session-identity profile id.
        conversation_id / chat_id: client-facing key resolving the session.
        audio: raw PCM16 bytes or a base64-encoded str (None on the ack path).
        soft: stage the frame (record-and-hold) instead of pushing it live.
        accept: ack — True flushes staged frames, False drops them.
        idempotency_key: staging key (paired with ``accept`` on the ack).
    """
    # AUTHN: a caller with no resolved profile is rejected outright.
    if not profile_id:
        return ChatSpeakResult(accepted=False, denied=True)

    session = resolve_speak_session(conversation_id, chat_id)
    if session is None:
        return ChatSpeakResult(accepted=False, not_found=True)

    # AUTHZ / ownership (the W1 guard — mirrors ws/attempt/speak.py:#149): only
    # the authenticated owner of the live session may push audio into it.
    # Fail-closed and owner-only (no role bypass). Compare stringified because
    # AudioSession.profile_id is stored as a str.
    if str(profile_id) != (session.profile_id or ""):
        return ChatSpeakResult(accepted=False, denied=True)

    # ── Ack: flush (accept) or drop (reject) the staged frames ──
    if accept is not None and idempotency_key is not None:
        key = str(idempotency_key)
        staged = session.pending_frames.pop(key, [])
        if accept:
            ok = all(_enqueue(session, f) for f in staged) if staged else True
            return ChatSpeakResult(accepted=ok, idempotency_key=key)
        return ChatSpeakResult(accepted=False, idempotency_key=key)

    # Decode / accept the inbound frame (required for stage + live push).
    audio_bytes: bytes | None = audio if isinstance(audio, bytes) else None
    if audio_bytes is None and isinstance(audio, str):
        try:
            audio_bytes = base64.b64decode(audio)
        except Exception:
            return ChatSpeakResult(accepted=False, bad_audio=True)
    if audio is None:
        # No audio supplied at all (and not an ack) — HTTP treats this as a 400.
        return ChatSpeakResult(accepted=False, bad_audio=True)
    if not audio_bytes:
        return ChatSpeakResult(accepted=False)

    # ── Soft propose: hold the frame, don't push it ──
    if soft:
        key = str(idempotency_key or uuid4())
        session.pending_frames.setdefault(key, []).append(audio_bytes)
        return ChatSpeakResult(accepted=True, idempotency_key=key)

    # ── Live: push immediately (real-time hot path) ──
    return ChatSpeakResult(accepted=_enqueue(session, audio_bytes))
