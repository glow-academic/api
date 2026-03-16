"""Descriptions CREATE — reusable data-access layer."""

from uuid import UUID

import asyncpg  # type: ignore
from redis.asyncio import Redis

from app.tools.resources.descriptions.get import get_descriptions
from app.tools.resources.descriptions.types import GetDescriptionResponse
from app.utils.cache.invalidate_tags import invalidate_tags


async def create_description(
    conn: asyncpg.Connection,
    description: str,
    redis: Redis,
    id: UUID | None = None,
    mcp: bool = False,
    soft: bool = False,
) -> GetDescriptionResponse:
    """Create a description resource."""
    description_id = await conn.fetchval(
        """
        INSERT INTO descriptions_resource (id, description, active, mcp, generated)
        VALUES (COALESCE($4, uuidv7()), $1, $2, $3, $3)
        RETURNING id
    """,
        description,
        not soft,
        mcp,
        id,
    )

    await invalidate_tags(["resources", "descriptions"], redis=redis)
    items = await get_descriptions(conn, [description_id], redis, bypass_cache=True)
    return items[0]
