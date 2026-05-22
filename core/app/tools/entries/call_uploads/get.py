"""Call Uploads GET — reusable data-access layer."""

from uuid import UUID

import asyncpg  # type: ignore
from redis.asyncio import Redis

from app.tools.entries.call_uploads.types import GetCallUploadResponse
from app.utils.cache.hedged_row import read_back_row


async def get_call_upload(
    conn: asyncpg.Connection,
    call_upload_id: UUID,
    redis: Redis,
    *,
    bypass_cache: bool = False,
) -> GetCallUploadResponse | None:
    """Get a call_uploads entry by ID."""
    if not bypass_cache:
        cached = await read_back_row(redis, "call_uploads", call_upload_id)
        if cached is not None:
            return GetCallUploadResponse.model_validate(cached)

    row = await conn.fetchrow(
        """
        SELECT id, call_id, upload_id, session_id,
               created_at, active, mcp, generated
        FROM call_uploads_entry
        WHERE id = $1
    """,
        call_upload_id,
    )

    if row is None:
        return None

    return GetCallUploadResponse(
        id=row["id"],
        call_id=row["call_id"],
        upload_id=row["upload_id"],
        session_id=row["session_id"],
        created_at=row["created_at"],
        active=row["active"],
        mcp=row["mcp"],
        generated=row["generated"],
    )
