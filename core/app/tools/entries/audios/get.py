"""Audios GET — reusable data-access layer."""

from uuid import UUID

import asyncpg  # type: ignore
from redis.asyncio import Redis

from app.tools.entries.audios.types import GetAudioResponse
from app.utils.cache.hedged_row import read_back_row


async def get_audio(
    conn: asyncpg.Connection,
    audio_id: UUID,
    redis: Redis,
    *,
    bypass_cache: bool = False,
) -> GetAudioResponse | None:
    """Get an audios entry by ID."""
    if not bypass_cache:
        cached = await read_back_row(redis, "audios", audio_id)
        if cached is not None:
            return GetAudioResponse.model_validate(cached)

    row = await conn.fetchrow(
        """
        SELECT id, session_id, length_seconds, active, mcp, generated
        FROM audios_entry
        WHERE id = $1
    """,
        audio_id,
    )

    if row is None:
        return None

    return GetAudioResponse(
        id=row["id"],
        session_id=row["session_id"],
        length_seconds=row["length_seconds"],
        active=row["active"],
        mcp=row["mcp"],
        generated=row["generated"],
    )
