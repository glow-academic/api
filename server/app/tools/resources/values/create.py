"""Values CREATE — reusable data-access layer."""

from uuid import UUID

import asyncpg  # type: ignore
from redis.asyncio import Redis

from app.tools.resources.values.get import get_values
from app.tools.resources.values.types import GetValueResponse
from app.utils.cache.invalidate_tags import invalidate_tags


async def create_value(
    conn: asyncpg.Connection,
    value: str,
    redis: Redis,
    id: UUID | None = None,
    mcp: bool = False,
    soft: bool = False,
    value_type: str = "model",
) -> GetValueResponse:
    """Create a value resource."""
    value_id = await conn.fetchval(
        """
        INSERT INTO values_resource (id, value, type, active, mcp, generated)
        VALUES (COALESCE($5, uuidv7()), $1, $2::value_type, $3, $4, $4)
        RETURNING id
    """,
        value,
        value_type,
        not soft,
        mcp,
        id,
    )

    await invalidate_tags(["resources", "values"], redis=redis)
    items = await get_values(conn, [value_id], redis, bypass_cache=True)
    return items[0]
