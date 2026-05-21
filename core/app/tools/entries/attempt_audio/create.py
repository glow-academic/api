"""Entry CREATE — reusable data-access layer for attempt_audio."""

from uuid import UUID

import asyncpg  # type: ignore
from redis.asyncio import Redis

from app.tools.entries.attempt_audio.types import CreateAttemptAudioResponse


async def create_attempt_audio(
    conn: asyncpg.Connection,
    redis: Redis,
    message_id: UUID,
    audios_id: UUID,
    session_id: UUID,
    id: UUID | None = None,
    mcp: bool = False,
    soft: bool = False,
) -> CreateAttemptAudioResponse:
    """Attach an audio (resource-level ``audios_id``) to a chat message.

    Mirrors the attempt_hint_entry pattern — each attachment is its own
    entry row with its own id, so messages can carry multiple audio
    attachments and per-attachment soft-delete remains possible.
    """
    entry_id = await conn.fetchval(
        """
        INSERT INTO attempt_audio_entry
            (id, message_id, audios_id, session_id, active, mcp, generated)
        VALUES (COALESCE($6, uuidv7()), $1, $2, $3, $4, $5, true)
        RETURNING id
        """,
        message_id,
        audios_id,
        session_id,
        not soft,
        mcp,
        id,
    )

    return CreateAttemptAudioResponse(id=entry_id)
