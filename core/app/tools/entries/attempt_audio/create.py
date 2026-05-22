"""Entry CREATE — reusable data-access layer for attempt_audio."""

from uuid import UUID

import asyncpg  # type: ignore
from redis.asyncio import Redis

from app.tools.entries.attempt_audio.types import CreateAttemptAudioResponse
from app.utils.cache.hedged_row import write_back_row


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
    row = await conn.fetchrow(
        """
        INSERT INTO attempt_audio_entry
            (id, message_id, audios_id, session_id, active, mcp, generated)
        VALUES (COALESCE($6, uuidv7()), $1, $2, $3, $4, $5, true)
        RETURNING id, created_at
        """,
        message_id,
        audios_id,
        session_id,
        not soft,
        mcp,
        id,
    )
    if row is None:
        raise ValueError("Failed to create attempt_audio entry")
    entry_id = row["id"]
    actual_created_at = row["created_at"]

    fresh_row = {
        "id": str(entry_id),
        "message_id": str(message_id),
        "audios_id": str(audios_id),
        "session_id": str(session_id),
        "active": not soft,
        "mcp": mcp,
        "generated": True,
        "created_at": actual_created_at.isoformat(),
    }
    await write_back_row(
        redis,
        "attempt_audio",
        entry_id,
        fresh_row,
        score_ms=int(actual_created_at.timestamp() * 1000),
    )

    return CreateAttemptAudioResponse(id=entry_id)
