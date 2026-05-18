"""Points CREATE — reusable data-access layer."""

from uuid import UUID

import asyncpg  # type: ignore
from redis.asyncio import Redis

from app.tools.resources.points.get import get_points
from app.tools.resources.points.types import GetPointResponse
from app.utils.cache.invalidate_tags import invalidate_tags


async def create_point(
    conn: asyncpg.Connection,
    value: int,
    redis: Redis,
    id: UUID | None = None,
    point_type: str = "total",
    mcp: bool = False,
    soft: bool = False,
) -> GetPointResponse:
    """Create a point resource (plain INSERT — no unique constraint)."""
    point_id = await conn.fetchval(
        """
        INSERT INTO points_resource (id, value, type, active, mcp, generated)
        VALUES (COALESCE($5, uuidv7()), $1, $2, $3, $4, $4)
        RETURNING id
        """,
        value,
        point_type,
        not soft,
        mcp,
        id,
    )

    await invalidate_tags(["resources", "points"], redis=redis)
    items = await get_points(conn, [point_id], redis, bypass_cache=True)
    return items[0]
