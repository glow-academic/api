"""Files CREATE — reusable data-access layer."""

from uuid import UUID

import asyncpg  # type: ignore
from redis.asyncio import Redis

from app.tools.resources.files.get import get_files
from app.tools.resources.files.types import GetFileResponse
from app.utils.cache.invalidate_tags import invalidate_tags


async def create_file(
    conn: asyncpg.Connection,
    redis: Redis,
    id: UUID | None = None,
    mcp: bool = False,
    soft: bool = False,
) -> GetFileResponse:
    """Create a file resource (plain insert, no unique constraint)."""
    file_id = await conn.fetchval(
        """
        INSERT INTO files_resource (id, active, mcp, generated)
        VALUES (COALESCE($3, uuidv7()), $1, $2, $2)
        RETURNING id
    """,
        not soft,
        mcp,
        id,
    )

    await invalidate_tags(["resources", "files"], redis=redis)
    items = await get_files(conn, [file_id], redis, bypass_cache=True)
    return items[0]
