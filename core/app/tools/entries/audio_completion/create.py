"""Entry CREATE — reusable data-access layer."""

from uuid import UUID

import asyncpg
from redis.asyncio import Redis

from app.tools.entries.audio_completion.types import (
    CreateAudioCompletionResponse,
)
from app.utils.cache.hedged_row import write_back_row


async def create_audio_completion(
    conn: asyncpg.Connection,
    redis: Redis,
    audio_id: UUID,
    session_id: UUID,
    id: UUID | None = None,
    stop: bool = False,
    error: bool = False,
    message: str = "",
    mcp: bool = False,
    soft: bool = False,
) -> CreateAudioCompletionResponse:
    """Create a audio_completion entry."""
    row = await conn.fetchrow(
        """
        INSERT INTO audio_completion_entry (id, audio_id, session_id, stop, error, message, active, mcp, generated)
        VALUES (COALESCE($8, uuidv7()), $1, $2, $3, $4, $5, $6, $7, true)
        RETURNING id, created_at
        """,
        audio_id,
        session_id,
        stop,
        error,
        message,
        not soft,
        mcp,
        id,
    )

    if row is None:
        raise ValueError("Failed to create audio_completion entry")

    entry_id = row["id"]
    created_at = row["created_at"]

    fresh_row = {
        "id": str(entry_id),
        "audio_id": str(audio_id),
        "stop": stop,
        "error": error,
        "message": message,
        "session_id": str(session_id),
        "created_at": created_at.isoformat(),
        "active": not soft,
        "generated": True,
        "mcp": mcp,
    }
    await write_back_row(
        redis,
        "audio_completion",
        entry_id,
        fresh_row,
        score_ms=int(created_at.timestamp() * 1000),
    )

    return CreateAudioCompletionResponse(id=entry_id)
