"""Voices CREATE — reusable data-access layer."""

from uuid import UUID

import asyncpg  # type: ignore
from redis.asyncio import Redis

from app.tools.resources.voices.get import get_voices
from app.tools.resources.voices.types import GetVoiceResponse
from app.utils.cache.invalidate_tags import invalidate_tags


async def create_voice(
    conn: asyncpg.Connection,
    voice: str,
    redis: Redis,
    id: UUID | None = None,
    mcp: bool = False,
    soft: bool = False,
) -> GetVoiceResponse:
    """Create a voice resource."""
    voice_id = await conn.fetchval(
        """
        INSERT INTO voices_resource (id, voice, active, mcp, generated)
        VALUES (COALESCE($4, uuidv7()), $1, $2, $3, $3)
        RETURNING id
    """,
        voice,
        not soft,
        mcp,
        id,
    )

    await invalidate_tags(["resources", "voices"], redis=redis)
    items = await get_voices(conn, [voice_id], redis, bypass_cache=True)
    return items[0]
