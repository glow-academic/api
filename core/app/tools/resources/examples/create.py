"""Examples CREATE — reusable data-access layer."""

from uuid import UUID

import asyncpg  # type: ignore
from redis.asyncio import Redis

from app.tools.resources.examples.get import get_examples
from app.tools.resources.examples.types import GetExampleResponse
from app.utils.cache.invalidate_tags import invalidate_tags


async def create_example(
    conn: asyncpg.Connection,
    example: str,
    redis: Redis,
    id: UUID | None = None,
    mcp: bool = False,
    soft: bool = False,
) -> GetExampleResponse:
    """Create an example resource."""
    example_id = await conn.fetchval(
        """
        INSERT INTO examples_resource (id, example, active, mcp, generated)
        VALUES (COALESCE($4, uuidv7()), $1, $2, $3, $3)
        RETURNING id
    """,
        example,
        not soft,
        mcp,
        id,
    )

    await invalidate_tags(["resources", "examples"], redis=redis)
    items = await get_examples(conn, [example_id], redis, bypass_cache=True)
    return items[0]
