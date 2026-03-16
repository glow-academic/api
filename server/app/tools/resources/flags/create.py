"""Flags CREATE — reusable data-access layer."""

from uuid import UUID

import asyncpg  # type: ignore
from redis.asyncio import Redis

from app.tools.resources.flags.get import get_flags
from app.tools.resources.flags.types import GetFlagResponse
from app.utils.cache.invalidate_tags import invalidate_tags


async def create_flag(
    conn: asyncpg.Connection,
    name: str,
    description: str,
    icon: str,
    redis: Redis,
    id: UUID | None = None,
    flag_type: str = "active",
    value: bool = True,
    mcp: bool = False,
    soft: bool = False,
) -> GetFlagResponse:
    """Create a flag resource."""
    flag_id = await conn.fetchval(
        """
        INSERT INTO flags_resource (id, name, description, icon, type, value, active, mcp, generated)
        VALUES (COALESCE($8, uuidv7()), $1, $2, $3, $4::flag_type, $5, $6, $7, $7)
        RETURNING id
    """,
        name,
        description,
        icon,
        flag_type,
        value,
        not soft,
        mcp,
        id,
    )

    await invalidate_tags(["resources", "flags"], redis=redis)
    items = await get_flags(conn, [flag_id], redis, bypass_cache=True)
    return items[0]
