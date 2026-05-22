"""Message Uploads GET — reusable data-access layer."""

from uuid import UUID

import asyncpg  # type: ignore
from redis.asyncio import Redis

from app.tools.entries.message_uploads.types import GetMessageUploadResponse
from app.utils.cache.hedged_row import read_back_row


async def get_message_upload(
    conn: asyncpg.Connection,
    message_upload_id: UUID,
    redis: Redis,
    *,
    bypass_cache: bool = False,
) -> GetMessageUploadResponse | None:
    """Get a message_uploads entry by ID."""
    if not bypass_cache:
        cached = await read_back_row(redis, "message_uploads", message_upload_id)
        if cached is not None:
            return GetMessageUploadResponse.model_validate(cached)

    row = await conn.fetchrow(
        """
        SELECT id, message_id, upload_id, session_id,
               created_at, active, mcp, generated
        FROM message_uploads_entry
        WHERE id = $1
    """,
        message_upload_id,
    )

    if row is None:
        return None

    return GetMessageUploadResponse(
        id=row["id"],
        message_id=row["message_id"],
        upload_id=row["upload_id"],
        session_id=row["session_id"],
        created_at=row["created_at"],
        active=row["active"],
        mcp=row["mcp"],
        generated=row["generated"],
    )
