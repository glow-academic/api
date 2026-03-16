"""Auth Item Values CREATE — reusable data-access layer."""

from uuid import UUID

import asyncpg  # type: ignore
from redis.asyncio import Redis

from app.tools.resources.auth_item_values.get import get_auth_item_values
from app.tools.resources.auth_item_values.types import (
    GetAuthItemValueResponse,
)
from app.utils.cache.invalidate_tags import invalidate_tags


async def create_auth_item_value(
    conn: asyncpg.Connection,
    auth_id: UUID,
    item_id: UUID,
    value: str,
    redis: Redis,
    id: UUID | None = None,
    mcp: bool = False,
    soft: bool = False,
) -> GetAuthItemValueResponse:
    """Create an auth_item_value resource (ON CONFLICT on (auth_id, item_id, value))."""
    row_id = await conn.fetchval(
        """
        INSERT INTO auth_item_values_resource (id, auth_id, item_id, value, active, mcp, generated)
        VALUES (COALESCE($6, uuidv7()), $1, $2, $3, $4, $5, $5)
        ON CONFLICT (auth_id, item_id, value) DO UPDATE SET auth_id = EXCLUDED.auth_id
        RETURNING id
        """,
        auth_id,
        item_id,
        value,
        not soft,
        mcp,
        id,
    )

    await invalidate_tags(["resources", "auth_item_values"], redis=redis)
    items = await get_auth_item_values(conn, [row_id], redis, bypass_cache=True)
    return items[0]
