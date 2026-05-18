"""Colors CREATE — reusable data-access layer."""

from uuid import UUID

import asyncpg  # type: ignore
from redis.asyncio import Redis

from app.tools.resources.colors.get import get_colors
from app.tools.resources.colors.types import GetColorResponse
from app.utils.cache.invalidate_tags import invalidate_tags


async def create_color(
    conn: asyncpg.Connection,
    name: str,
    description: str,
    hex_code: str,
    redis: Redis,
    id: UUID | None = None,
    color_type: str = "primary",
    mcp: bool = False,
    soft: bool = False,
) -> GetColorResponse:
    """Create a color resource."""
    color_id = await conn.fetchval(
        """
        INSERT INTO colors_resource (id, name, description, hex_code, type, active, mcp, generated)
        VALUES (COALESCE($7, uuidv7()), $1, $2, $3, $4, $5, $6, $6)
        RETURNING id
    """,
        name,
        description,
        hex_code,
        color_type,
        not soft,
        mcp,
        id,
    )

    await invalidate_tags(["resources", "colors"], redis=redis)
    items = await get_colors(conn, [color_id], redis, bypass_cache=True)
    return items[0]
