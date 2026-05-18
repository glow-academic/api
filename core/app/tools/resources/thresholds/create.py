"""Thresholds CREATE — reusable data-access layer."""

from uuid import UUID

import asyncpg  # type: ignore
from redis.asyncio import Redis

from app.tools.resources.thresholds.get import get_thresholds
from app.tools.resources.thresholds.types import GetThresholdResponse
from app.utils.cache.invalidate_tags import invalidate_tags


async def create_threshold(
    conn: asyncpg.Connection,
    value: int,
    redis: Redis,
    id: UUID | None = None,
    threshold_type: str = "success",
    mcp: bool = False,
    soft: bool = False,
) -> GetThresholdResponse:
    """Create a threshold resource (plain INSERT — no unique constraint)."""
    threshold_id = await conn.fetchval(
        """
        INSERT INTO thresholds_resource (id, value, type, active, mcp, generated)
        VALUES (COALESCE($5, uuidv7()), $1, $2, $3, $4, $4)
        RETURNING id
        """,
        value,
        threshold_type,
        not soft,
        mcp,
        id,
    )

    await invalidate_tags(["resources", "thresholds"], redis=redis)
    items = await get_thresholds(conn, [threshold_id], redis, bypass_cache=True)
    return items[0]
