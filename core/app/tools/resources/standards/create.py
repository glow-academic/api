"""Standards CREATE — reusable data-access layer."""

from uuid import UUID

import asyncpg  # type: ignore
from redis.asyncio import Redis

from app.tools.resources.standards.get import get_standards
from app.tools.resources.standards.types import GetStandardResponse
from app.utils.cache.invalidate_tags import invalidate_tags


async def create_standard(
    conn: asyncpg.Connection,
    name: str,
    description: str,
    points: int,
    standard_group_id: UUID,
    redis: Redis,
    id: UUID | None = None,
    mcp: bool = False,
    soft: bool = False,
) -> GetStandardResponse:
    """Create a standard resource (plain INSERT — no unique constraint)."""
    row_id = await conn.fetchval(
        """
        INSERT INTO standards_resource
            (id, name, description, points, standard_group_id, active, mcp, generated)
        VALUES (COALESCE($7, uuidv7()), $1, $2, $3, $4, $5, $6, $6)
        RETURNING id
        """,
        name,
        description,
        points,
        standard_group_id,
        not soft,
        mcp,
        id,
    )

    await invalidate_tags(["resources", "standards"], redis=redis)
    items = await get_standards(conn, [row_id], redis, bypass_cache=True)
    return items[0]
