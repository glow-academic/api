"""Internal impl for attempt_chat_silence — shared by WebSocket and HTTP.

Records conversation completion in DB and emits attempt.generate.audio.session_complete.
"""

import uuid as uuid_mod
from typing import Any

from pydantic import BaseModel

from app.infra.globals import get_internal_sio, get_pool
from app.infra.websocket.attempt_types import AttemptAudioEndedData
from app.infra.websocket.audio_lifecycle import cleanup_audio_session
from app.infra.websocket.session_store import get_session_by_chat_id
from app.tools.entries.attempt_conversation_completion.create import (
    create_attempt_conversation_completion,
)
from app.utils.logging.db_logger import get_logger

logger = get_logger(__name__)


class AudioStopInternalResult(BaseModel):
    """Structured result for audio stop orchestration."""

    chat_id: str
    stopped: bool = True


async def attempt_chat_silence_internal_impl(
    data: dict[str, Any],
) -> AudioStopInternalResult:
    """Run canonical audio stop orchestration for any surface.

    Required data keys: chat_id.
    Optional: sid (empty string for HTTP callers).
    """
    chat_id = data.get("chat_id")
    if not chat_id:
        raise ValueError("Missing chat_id for attempt_chat_silence")

    sid = data.get("sid", "")

    session = get_session_by_chat_id(str(chat_id))
    if not session:
        # Silence on a non-existent session is a no-op — the voice session
        # already ended or never started. Still return a success result so
        # the client doesn't need to branch on "was there a session?".
        logger.info(
            f"attempt_chat_silence: no session for chat_id={chat_id} (no-op)"
        )
        return AudioStopInternalResult(chat_id=str(chat_id), stopped=False)

    group_id = session.group_id

    # Record conversation completion in DB
    if session.conversation_id and session.session_id:
        try:
            pool = get_pool()
            async with pool.acquire() as conn:
                await create_attempt_conversation_completion(
                    conn,
                    conversation_id=uuid_mod.UUID(session.conversation_id),
                    session_id=uuid_mod.UUID(str(session.session_id)),
                    stop=True,
                )
        except Exception as e:
            logger.warning(f"Failed to record conversation completion: {e}")

    # Clean up the realtime adapter session, then emit:
    #   - the canonical session_complete event (kept for log filter +
    #     observability)
    #   - the client-facing voice_ended signal that closes the mic UI
    # Previously the rename + cleanup lived in
    # ``ws/output/attempt/generate/audio_session_complete.py`` →
    # ``audio_stop_impl``. Inlined here so the workflow reads
    # top-to-bottom at the originating impl.
    await cleanup_audio_session(session)

    internal_sio = get_internal_sio()
    await internal_sio.emit(
        "attempt.generate.audio.session_complete",
        {
            "group_id": group_id,
            "sid": sid,
        },
    )
    await internal_sio.emit(
        "attempt.chat.voice_ended",
        AttemptAudioEndedData(
            sid=sid,
            chat_id=str(chat_id),
            group_id=group_id,
            success=True,
            message="Voice session stopped",
            rooms=[session.profile_id] if session.profile_id else None,
        ).model_dump(mode="json"),
    )

    return AudioStopInternalResult(chat_id=str(chat_id))
