"""Standard Groups CREATE — reusable data-access layer."""

from uuid import UUID

import asyncpg  # type: ignore
from redis.asyncio import Redis

from app.tools.resources.standard_groups.get import get_standard_groups
from app.tools.resources.standard_groups.types import GetStandardGroupResponse
from app.utils.cache.invalidate_tags import invalidate_tags


async def create_standard_group(
    conn: asyncpg.Connection,
    name: str,
    short_name: str,
    description: str,
    points: int,
    pass_points: int,
    redis: Redis,
    id: UUID | None = None,
    mcp: bool = False,
    soft: bool = False,
) -> GetStandardGroupResponse:
    """Create a standard_group resource (plain INSERT, no unique constraint)."""
    sg_id = await conn.fetchval(
        """
        INSERT INTO standard_groups_resource
            (id, name, short_name, description, points, pass_points, active, mcp, generated)
        VALUES (COALESCE($8, uuidv7()), $1, $2, $3, $4, $5, $6, $7, $7)
        RETURNING id
        """,
        name,
        short_name,
        description,
        points,
        pass_points,
        not soft,
        mcp,
        id,
    )
    await invalidate_tags(["resources", "standard_groups"], redis=redis)
    items = await get_standard_groups(conn, [sg_id], redis, bypass_cache=True)
    return items[0]
