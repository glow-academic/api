"""Options CREATE — reusable data-access layer."""

from uuid import UUID

import asyncpg  # type: ignore
from redis.asyncio import Redis

from app.tools.resources.options.get import get_options
from app.tools.resources.options.types import GetOptionResponse
from app.utils.cache.invalidate_tags import invalidate_tags


async def create_option(
    conn: asyncpg.Connection,
    option_text: str,
    redis: Redis,
    id: UUID | None = None,
    mcp: bool = False,
    soft: bool = False,
    question_id: UUID | None = None,
) -> GetOptionResponse:
    """Create an option resource (plain INSERT, no unique constraint)."""
    option_id = await conn.fetchval(
        """
        INSERT INTO options_resource (id, option_text, question_id, active, mcp, generated)
        VALUES (COALESCE($5, uuidv7()), $1, $2, $3, $4, $4)
        RETURNING id
        """,
        option_text,
        question_id,
        not soft,
        mcp,
        id,
    )
    await invalidate_tags(["resources", "options"], redis=redis)
    items = await get_options(conn, [option_id], redis, bypass_cache=True)
    return items[0]
