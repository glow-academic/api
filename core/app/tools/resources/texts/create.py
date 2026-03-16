"""Texts CREATE — reusable data-access layer."""

from uuid import UUID

import asyncpg  # type: ignore
from redis.asyncio import Redis

from app.tools.resources.texts.get import get_texts
from app.tools.resources.texts.types import GetTextResponse
from app.utils.cache.invalidate_tags import invalidate_tags


async def create_text(
    conn: asyncpg.Connection,
    redis: Redis,
    id: UUID | None = None,
    mcp: bool = False,
    soft: bool = False,
) -> GetTextResponse:
    """Create a text resource."""
    text_id = await conn.fetchval(
        """
        INSERT INTO texts_resource (id, active, mcp, generated)
        VALUES (COALESCE($3, uuidv7()), $1, $2, $2)
        RETURNING id
    """,
        not soft,
        mcp,
        id,
    )

    await invalidate_tags(["resources", "texts"], redis=redis)
    items = await get_texts(conn, [text_id], redis, bypass_cache=True)
    return items[0]
