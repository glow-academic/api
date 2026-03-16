"""Internal impl for attempt_audio_stop — shared by WebSocket and HTTP.

Records conversation completion in DB and emits generate_audio_session_complete.
"""

import uuid as uuid_mod
from typing import Any

from pydantic import BaseModel

from app.infra.globals import get_internal_sio, get_pool
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


async def attempt_audio_stop_internal_impl(
    data: dict[str, Any],
) -> AudioStopInternalResult:
    """Run canonical audio stop orchestration for any surface.

    Required data keys: chat_id.
    Optional: sid (empty string for HTTP callers).
    """
    chat_id = data.get("chat_id")
    if not chat_id:
        raise ValueError("Missing chat_id for attempt_audio_stop")

    sid = data.get("sid", "")

    session = get_session_by_chat_id(str(chat_id))
    if not session:
        raise ValueError(f"No active audio session for chat {chat_id}")

    group_id = session.group_id

    # Record conversation completion in DB
    if session.conversation_id:
        try:
            pool = get_pool()
            async with pool.acquire() as conn:
                await create_attempt_conversation_completion(
                    conn,
                    conversation_id=uuid_mod.UUID(session.conversation_id),
                    call_id=uuid_mod.uuid4(),
                    stop=True,
                )
        except Exception as e:
            logger.warning(f"Failed to record conversation completion: {e}")

    internal_sio = get_internal_sio()
    await internal_sio.emit(
        "generate_audio_session_complete",
        {
            "group_id": group_id,
            "sid": sid,
        },
    )

    return AudioStopInternalResult(chat_id=str(chat_id))
