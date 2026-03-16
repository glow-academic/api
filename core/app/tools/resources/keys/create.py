"""Keys CREATE — reusable data-access layer."""

from uuid import UUID

import asyncpg  # type: ignore
from redis.asyncio import Redis

from app.tools.resources.keys.get import get_keys
from app.tools.resources.keys.types import GetKeyResponse
from app.utils.cache.invalidate_tags import invalidate_tags


async def create_key(
    conn: asyncpg.Connection,
    redis: Redis,
    id: UUID | None = None,
    name: str = "",
    mcp: bool = False,
    soft: bool = False,
    key: str = "",
    description: str = "",
) -> GetKeyResponse:
    """Create a key resource (plain INSERT — no unique constraint)."""
    key_id = await conn.fetchval(
        """
        INSERT INTO keys_resource (id, key, name, description, active, mcp, generated)
        VALUES (COALESCE($6, uuidv7()), $1, $2, $3, $4, $5, $5)
        RETURNING id
        """,
        key,
        name,
        description,
        not soft,
        mcp,
        id,
    )

    await invalidate_tags(["resources", "keys"], redis=redis)
    items = await get_keys(conn, [key_id], redis, bypass_cache=True)
    return items[0]
