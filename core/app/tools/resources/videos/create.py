"""Videos CREATE — reusable data-access layer."""

from uuid import UUID

import asyncpg  # type: ignore
from redis.asyncio import Redis

from app.tools.resources.videos.get import get_videos
from app.tools.resources.videos.types import GetVideoResponse
from app.utils.cache.invalidate_tags import invalidate_tags


async def create_video(
    conn: asyncpg.Connection,
    name: str,
    description: str,
    redis: Redis,
    id: UUID | None = None,
    mcp: bool = False,
    soft: bool = False,
) -> GetVideoResponse:
    """Create a video resource."""
    video_id = await conn.fetchval(
        """
        INSERT INTO videos_resource (id, name, description, active, mcp, generated)
        VALUES (COALESCE($5, uuidv7()), $1, $2, $3, $4, $4)
        RETURNING id
    """,
        name,
        description,
        not soft,
        mcp,
        id,
    )

    await invalidate_tags(["resources", "videos"], redis=redis)
    items = await get_videos(conn, [video_id], redis, bypass_cache=True)
    return items[0]
