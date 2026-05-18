"""Items CREATE — reusable data-access layer."""

from uuid import UUID

import asyncpg  # type: ignore
from redis.asyncio import Redis

from app.tools.resources.items.get import get_items
from app.tools.resources.items.types import GetItemResponse
from app.utils.cache.invalidate_tags import invalidate_tags


async def create_item(
    conn: asyncpg.Connection,
    name: str,
    description: str,
    redis: Redis,
    id: UUID | None = None,
    mcp: bool = False,
    soft: bool = False,
    encrypted: bool = False,
    position: int = 0,
) -> GetItemResponse:
    """Create an item resource (plain INSERT — no unique constraint)."""
    item_id = await conn.fetchval(
        """
        INSERT INTO items_resource (id, name, description, encrypted, position, active, mcp, generated)
        VALUES (COALESCE($7, uuidv7()), $1, $2, $3, $4, $5, $6, $6)
        RETURNING id
        """,
        name,
        description,
        encrypted,
        position,
        not soft,
        mcp,
        id,
    )

    await invalidate_tags(["resources", "items"], redis=redis)
    items = await get_items(conn, [item_id], redis, bypass_cache=True)
    return items[0]
