"""Auth Item Keys CREATE — reusable data-access layer."""

from datetime import datetime
from uuid import UUID

import asyncpg  # type: ignore
from redis.asyncio import Redis

from app.tools.resources.auth_item_keys.get import get_auth_item_keys
from app.tools.resources.auth_item_keys.types import GetAuthItemKeyResponse
from app.utils.cache.invalidate_tags import invalidate_tags


async def create_auth_item_key(
    conn: asyncpg.Connection,
    auth_id: UUID,
    item_id: UUID,
    key_id: UUID,
    redis: Redis,
    id: UUID | None = None,
    updated_at: datetime | None = None,
    mcp: bool = False,
    soft: bool = False,
) -> GetAuthItemKeyResponse:
    """Create an auth_item_key resource (ON CONFLICT on (auth_id, item_id, key_id))."""
    row_id = await conn.fetchval(
        """
        INSERT INTO auth_item_keys_resource (id, auth_id, item_id, key_id, active, mcp, generated)
        VALUES (COALESCE($6, uuidv7()), $1, $2, $3, $4, $5, $5)
        ON CONFLICT (auth_id, item_id, key_id) DO UPDATE SET auth_id = EXCLUDED.auth_id
        RETURNING id
        """,
        auth_id,
        item_id,
        key_id,
        not soft,
        mcp,
        id,
    )

    await invalidate_tags(["resources", "auth_item_keys"], redis=redis)
    items = await get_auth_item_keys(conn, [row_id], redis, bypass_cache=True)
    return items[0]
