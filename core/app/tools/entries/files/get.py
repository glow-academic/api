"""Files GET — reusable data-access layer."""

from uuid import UUID

import asyncpg  # type: ignore
from redis.asyncio import Redis

from app.tools.entries.files.types import GetFileResponse
from app.utils.cache.hedged_row import read_back_row


async def get_file(
    conn: asyncpg.Connection,
    file_id: UUID,
    redis: Redis,
    *,
    bypass_cache: bool = False,
) -> GetFileResponse | None:
    """Get a files entry by ID."""
    if not bypass_cache:
        cached = await read_back_row(redis, "files", file_id)
        if cached is not None:
            return GetFileResponse.model_validate(cached)

    row = await conn.fetchrow(
        """
        SELECT id, session_id, active, mcp, generated
        FROM files_entry
        WHERE id = $1
    """,
        file_id,
    )

    if row is None:
        return None

    return GetFileResponse(
        id=row["id"],
        session_id=row["session_id"],
        active=row["active"],
        mcp=row["mcp"],
        generated=row["generated"],
    )
