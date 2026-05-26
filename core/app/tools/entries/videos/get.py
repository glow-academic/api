"""Videos GET — reusable data-access layer."""

from uuid import UUID

import asyncpg  # type: ignore
from redis.asyncio import Redis

from app.tools.entries.videos.types import GetVideoResponse
from app.utils.cache.hedged_row import read_back_row


async def get_video(
    conn: asyncpg.Connection,
    video_id: UUID,
    redis: Redis,
    *,
    bypass_cache: bool = False,
) -> GetVideoResponse | None:
    """Get a videos entry by ID."""
    if not bypass_cache:
        cached = await read_back_row(redis, "videos", video_id)
        if cached is not None:
            return GetVideoResponse.model_validate(cached)

    row = await conn.fetchrow(
        """
        SELECT id, session_id, length_seconds, active, mcp, generated
        FROM videos_entry
        WHERE id = $1
    """,
        video_id,
    )

    if row is None:
        return None

    return GetVideoResponse(
        id=row["id"],
        session_id=row["session_id"],
        length_seconds=row["length_seconds"],
        active=row["active"],
        mcp=row["mcp"],
        generated=row["generated"],
    )
