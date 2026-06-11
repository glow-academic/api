"""Input: attempt.chat_mute — toggle the live voice session's mic mute.

Fire-and-forget primitive, mirrors ``attempt.chat_speak`` (ws/attempt/speak.py):
no audit, no DB. Pushes a ``mic.set_muted`` control message onto the
session's inbound queue, where the realtime audio adapter's uplink loop
(``infra/websocket/adapters/audio/realtime.py``) applies it to
``session.muted`` — muted frames are dropped before reaching the provider.

Without this handler the client-emitted ``attempt.chat_mute`` event had no
``sio.on`` listener, so python-socketio sent no ack and the client's WS
command channel hung for the full 30s timeout on every mic toggle.
"""

import asyncio
from typing import Any

from app.infra.globals import sio
from app.infra.identity.socket import resolve_socket_identity
from app.infra.websocket.session_store import (
    get_session_by_chat_id,
    get_session_by_conversation_id,
)


@sio.on("attempt.chat_mute")  # type: ignore
async def attempt_chat_mute(sid: str, data: dict[str, Any]) -> None:
    # AUTHN: reject sockets with no stored identity (mirrors chat_speak, #149).
    identity = await resolve_socket_identity(sid)
    if not identity:
        return

    conversation_id = data.get("conversation_id")
    chat_id = data.get("chat_id")
    muted = bool(data.get("muted", False))

    # Resolve the live session (conversation_id preferred, chat_id fallback).
    session = None
    if conversation_id:
        session = get_session_by_conversation_id(str(conversation_id))
    elif chat_id:
        session = get_session_by_chat_id(str(chat_id))

    if not session:
        # No live session — mute on a non-existent session is a no-op.
        return

    # AUTHZ / ownership: only the authenticated owner of the live session may
    # mutate its mic state (mirrors chat_speak's owner-only IDOR gate, #149).
    if str(identity.profile_id) != session.profile_id:
        return

    try:
        session.inbound_queue.put_nowait({"type": "mic.set_muted", "muted": muted})
    except asyncio.QueueFull:
        pass
