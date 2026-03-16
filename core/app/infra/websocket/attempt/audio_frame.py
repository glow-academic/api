"""Internal impl for attempt_audio_frame — shared by WebSocket and HTTP.

Pushes raw audio bytes into the session's inbound queue with backpressure handling.
"""

import asyncio
import time
from uuid import UUID

from app.infra.websocket.session_store import get_session_by_chat_id


def attempt_audio_frame_internal_impl(
    *,
    chat_id: str | UUID,
    audio: bytes,
) -> bool:
    """Push audio bytes into the session inbound queue.

    Returns True if frame was accepted, False if dropped (backpressure) or no session.
    Synchronous — no async DB calls needed.
    """
    session = get_session_by_chat_id(str(chat_id))
    if not session:
        return False

    if not audio:
        return False

    session.last_activity = time.monotonic()
    try:
        session.inbound_queue.put_nowait({"type": "audio", "pcm16_bytes": audio})
        return True
    except asyncio.QueueFull:
        return False  # Backpressure: drop frame
