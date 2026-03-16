"""Qualities CREATE — reusable data-access layer."""

from uuid import UUID

import asyncpg  # type: ignore
from redis.asyncio import Redis

from app.tools.resources.qualities.get import get_qualities
from app.tools.resources.qualities.types import GetQualityResponse
from app.utils.cache.invalidate_tags import invalidate_tags


async def create_quality(
    conn: asyncpg.Connection,
    quality: str,
    redis: Redis,
    id: UUID | None = None,
    mcp: bool = False,
    soft: bool = False,
) -> GetQualityResponse:
    """Create a quality resource (plain INSERT — no unique constraint)."""
    quality_id = await conn.fetchval(
        """
        INSERT INTO qualities_resource (id, quality, active, mcp, generated)
        VALUES (COALESCE($4, uuidv7()), $1::quality_type, $2, $3, $3)
        RETURNING id
        """,
        quality,
        not soft,
        mcp,
        id,
    )

    await invalidate_tags(["resources", "qualities"], redis=redis)
    items = await get_qualities(conn, [quality_id], redis, bypass_cache=True)
    return items[0]
