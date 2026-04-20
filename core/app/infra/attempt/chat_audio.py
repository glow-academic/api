"""Attempt chat_audio — attach an audio asset to a chat message.

Post-hoc attachment: the message is already created (via
``/attempt/chat/message``), and this endpoint records the audio-message
link in ``attempt_audio_entry``. Mirrors the attempt_hint pattern.

The realtime adapter calls this server-internally for assistant turns:
the model's ``Attempt_Chat_Message`` tool call returns a ``message_id``
and the adapter's assistant audio capture yields an ``audios_id``; both
flow through here so clients only see fully-linked messages via the MV.
"""

from __future__ import annotations

from uuid import UUID

import asyncpg
from fastapi import HTTPException
from pydantic import BaseModel
from redis.asyncio import Redis

from app.infra.profile_identity_context import resolve_profile_identity_context
from app.tools.entries.attempt_audio.create import create_attempt_audio
from app.utils.cache.invalidate_tags import invalidate_tags


class AttemptChatAudioInternalResult(BaseModel):
    success: bool
    attempt_audio_id: str


async def attempt_chat_audio_internal_impl(
    pool: asyncpg.Pool,
    redis: Redis,
    *,
    profile_id: UUID,
    session_id: UUID | None = None,
    message_id: UUID,
    audios_id: UUID,
) -> AttemptChatAudioInternalResult:
    """Create an ``attempt_audio_entry`` row linking ``message_id`` to
    ``audios_id``. Returns the new entry's id.
    """
    profile = await resolve_profile_identity_context(
        pool, profile_id, redis, session_id=session_id,
    )
    if profile is None:
        raise HTTPException(
            status_code=401, detail="Profile not found. Please sign in again.",
        )

    effective_session_id = session_id or profile.session_id
    if effective_session_id is None:
        raise HTTPException(
            status_code=400, detail="session_id is required for attempt_chat_audio.",
        )

    async with pool.acquire() as conn:
        result = await create_attempt_audio(
            conn,
            message_id=message_id,
            audios_id=audios_id,
            session_id=effective_session_id,
        )

    await invalidate_tags(["entries", "attempt", "attempt_audio"], redis=redis)

    return AttemptChatAudioInternalResult(
        success=True, attempt_audio_id=str(result.id),
    )
