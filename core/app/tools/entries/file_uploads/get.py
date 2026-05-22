"""File Uploads GET — reusable data-access layer."""

from uuid import UUID

import asyncpg  # type: ignore
from redis.asyncio import Redis

from app.tools.entries.file_uploads.types import GetFileUploadResponse
from app.utils.cache.hedged_row import read_back_row


async def get_file_upload(
    conn: asyncpg.Connection,
    file_upload_id: UUID,
    redis: Redis,
    *,
    bypass_cache: bool = False,
) -> GetFileUploadResponse | None:
    """Get a file_uploads entry by ID."""
    if not bypass_cache:
        cached = await read_back_row(redis, "file_uploads", file_upload_id)
        if cached is not None:
            return GetFileUploadResponse.model_validate(cached)

    row = await conn.fetchrow(
        """
        SELECT id, file_id, upload_id, session_id,
               created_at, active, mcp, generated
        FROM file_uploads_entry
        WHERE id = $1
    """,
        file_upload_id,
    )

    if row is None:
        return None

    return GetFileUploadResponse(
        id=row["id"],
        file_id=row["file_id"],
        upload_id=row["upload_id"],
        session_id=row["session_id"],
        created_at=row["created_at"],
        active=row["active"],
        mcp=row["mcp"],
        generated=row["generated"],
    )
