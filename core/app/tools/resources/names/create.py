"""Names CREATE — reusable data-access layer."""

from uuid import UUID

import asyncpg  # type: ignore
from redis.asyncio import Redis

from app.tools.resources.names.get import get_names
from app.tools.resources.names.types import GetNameResponse
from app.utils.cache.invalidate_tags import invalidate_tags


async def create_name(
    conn: asyncpg.Connection,
    name: str,
    redis: Redis,
    id: UUID | None = None,
    mcp: bool = False,
    soft: bool = False,
) -> GetNameResponse:
    """Create a name resource (insert or get existing)."""
    name_id = await conn.fetchval(
        """
        INSERT INTO names_resource (id, name, active, mcp, generated)
        VALUES (COALESCE($4, uuidv7()), $1, $2, $3, $3)
        ON CONFLICT (name) DO UPDATE SET name = EXCLUDED.name
        RETURNING id
    """,
        name,
        not soft,
        mcp,
        id,
    )

    await invalidate_tags(["resources", "names"], redis=redis)
    items = await get_names(conn, [name_id], redis, bypass_cache=True)
    return items[0]
