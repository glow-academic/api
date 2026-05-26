"""Message Uploads CREATE — reusable data-access layer."""

from uuid import UUID

import asyncpg  # type: ignore
from redis.asyncio import Redis

from app.tools.entries.message_uploads.types import (
    CreateMessageUploadResponse,
)
from app.utils.cache.hedged_row import invalidate_row, write_back_row


async def create_message_upload(
    conn: asyncpg.Connection,
    redis: Redis,
    message_id: UUID,
    upload_id: UUID,
    session_id: UUID,
    id: UUID | None = None,
    mcp: bool = False,
    soft: bool = False,
) -> CreateMessageUploadResponse:
    """Create a message_uploads entry."""
    row = await conn.fetchrow(
        """
        INSERT INTO message_uploads_entry (id, message_id, upload_id, session_id, active, mcp, generated)
        VALUES (COALESCE($6, uuidv7()), $1, $2, $3, $4, $5, true)
        RETURNING id, created_at
    """,
        message_id,
        upload_id,
        session_id,
        not soft,
        mcp,
        id,
    )

    if row is None:
        raise ValueError("Failed to create message_uploads entry")

    row_id = row["id"]
    actual_created_at = row["created_at"]

    fresh_row = {
        "id": str(row_id),
        "message_id": str(message_id),
        "upload_id": str(upload_id),
        "session_id": str(session_id),
        "created_at": actual_created_at.isoformat(),
        "active": not soft,
        "mcp": mcp,
        "generated": True,
    }
    await write_back_row(
        redis,
        "message_uploads",
        row_id,
        fresh_row,
        score_ms=int(actual_created_at.timestamp() * 1000),
    )
    # Parent message + attempt_message cache rows hold empty *_ids arrays
    # until the upload links in via this junction. Invalidate both so the
    # next read falls through to the MV.
    await invalidate_row(redis, "messages", message_id)
    await invalidate_row(redis, "attempt_message", message_id)

    return CreateMessageUploadResponse(id=row_id)
