"""Input: attempt.chat.speak — push audio bytes into a conversation buffer.

No audit, no DB. Just pushes bytes into the session's inbound queue.
Keyed on conversation_id (or chat_id to resolve it).
"""

import asyncio
import time
from typing import Any

from app.infra.globals import sio
from app.infra.websocket.session_store import (
    get_session_by_chat_id,
    get_session_by_conversation_id,
)


@sio.on("attempt.chat.speak")  # type: ignore
async def attempt_chat_speak(sid: str, data: dict[str, Any]) -> None:
    conversation_id = data.get("conversation_id")
    chat_id = data.get("chat_id")
    audio = data.get("audio")
    if not audio:
        return

    # Resolve session
    session = None
    if conversation_id:
        session = get_session_by_conversation_id(str(conversation_id))
    elif chat_id:
        session = get_session_by_chat_id(str(chat_id))

    if not session:
        return

    audio_bytes = audio if isinstance(audio, bytes) else None
    if audio_bytes is None and isinstance(audio, str):
        import base64
        try:
            audio_bytes = base64.b64decode(audio)
        except Exception:
            return

    if not audio_bytes:
        return

    session.last_activity = time.monotonic()
    try:
        session.inbound_queue.put_nowait({"type": "audio", "pcm16_bytes": audio_bytes})
    except asyncio.QueueFull:
        pass
