"""Icons CREATE — reusable data-access layer."""

from uuid import UUID

import asyncpg  # type: ignore
from redis.asyncio import Redis

from app.tools.resources.icons.get import get_icons
from app.tools.resources.icons.types import GetIconResponse
from app.utils.cache.invalidate_tags import invalidate_tags


async def create_icon(
    conn: asyncpg.Connection,
    name: str,
    description: str,
    value: str,
    redis: Redis,
    id: UUID | None = None,
    mcp: bool = False,
    soft: bool = False,
) -> GetIconResponse:
    """Create an icon resource."""
    icon_id = await conn.fetchval(
        """
        INSERT INTO icons_resource (id, name, description, value, active, mcp, generated)
        VALUES (COALESCE($6, uuidv7()), $1, $2, $3, $4, $5, $5)
        RETURNING id
    """,
        name,
        description,
        value,
        not soft,
        mcp,
        id,
    )

    await invalidate_tags(["resources", "icons"], redis=redis)
    items = await get_icons(conn, [icon_id], redis, bypass_cache=True)
    return items[0]
