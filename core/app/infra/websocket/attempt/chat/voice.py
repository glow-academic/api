"""Internal impl for attempt_chat_voice — shared by WebSocket and HTTP.

Canonical per generate redesign: opens a realtime conversation and returns
its id. No AI dispatch here — the client separately calls /attempt/generate
with the returned conversation_id.
"""

import uuid
from typing import Any

from pydantic import BaseModel

from app.infra.attempt.client_types import AttemptAudioStartPayload
from app.infra.attempt.group import group_attempt_impl
from app.infra.globals import get_pool, get_redis_client
from app.tools.entries.attempt_chat.get import get_attempt_chats
from app.tools.entries.attempt_conversations.create import (
    create_attempt_conversations,
)
from app.utils.logging.db_logger import get_logger

logger = get_logger(__name__)


class AudioStartInternalResult(BaseModel):
    """Structured result for audio start orchestration."""

    chat_id: str
    attempt_id: str
    conversation_id: str
    group_id: str


async def attempt_chat_voice_internal_impl(
    data: dict[str, Any],
) -> AudioStartInternalResult:
    """Open a realtime conversation for a chat and return its id.

    Required data keys: chat_id, profile_id, session_id.

    This endpoint does NOT trigger AI generation. The client calls
    /attempt/generate with modalities + conversation_id separately.
    """
    redis = get_redis_client()
    payload = AttemptAudioStartPayload(**data)
    chat_id = payload.chat_id

    profile_id_str = data.get("profile_id")
    if not profile_id_str:
        raise ValueError("Missing profile_id for attempt_chat_voice")

    session_id_str = data.get("session_id")
    if not session_id_str:
        raise ValueError("Missing session_id for attempt_chat_voice")

    profile_id = uuid.UUID(str(profile_id_str))
    session_id = uuid.UUID(str(session_id_str))

    pool = get_pool()
    redis = get_redis_client()

    group_result = await group_attempt_impl(
        pool, redis, profile_id=profile_id, session_id=session_id,
    )
    group_id = group_result.group_id

    async with pool.acquire() as conn:
        chat_entries = await get_attempt_chats(conn, [chat_id], redis)
        if not chat_entries:
            raise ValueError(f"Attempt chat {chat_id} not found")
        attempt_id = chat_entries[0].attempt_id

        conversation = await create_attempt_conversations(
            conn, redis,
            chat_id=chat_id,
            session_id=session_id,
        )

    return AudioStartInternalResult(
        chat_id=str(chat_id),
        attempt_id=str(attempt_id),
        conversation_id=str(conversation.id),
        group_id=str(group_id),
    )
