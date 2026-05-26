"""Call Uploads CREATE — reusable data-access layer."""

from uuid import UUID

import asyncpg  # type: ignore
from redis.asyncio import Redis

from app.tools.entries.call_uploads.types import CreateCallUploadResponse
from app.utils.cache.hedged_row import invalidate_row, write_back_row


async def create_call_upload(
    conn: asyncpg.Connection,
    redis: Redis,
    call_id: UUID,
    upload_id: UUID,
    session_id: UUID,
    id: UUID | None = None,
    mcp: bool = False,
    soft: bool = False,
) -> CreateCallUploadResponse:
    """Create a call_uploads entry."""
    row = await conn.fetchrow(
        """
        INSERT INTO call_uploads_entry (id, call_id, upload_id, session_id, active, mcp, generated)
        VALUES (COALESCE($6, uuidv7()), $1, $2, $3, $4, $5, true)
        RETURNING id, created_at
    """,
        call_id,
        upload_id,
        session_id,
        not soft,
        mcp,
        id,
    )

    if row is None:
        raise ValueError("Failed to create call_uploads entry")

    row_id = row["id"]
    actual_created_at = row["created_at"]

    fresh_row = {
        "id": str(row_id),
        "call_id": str(call_id),
        "upload_id": str(upload_id),
        "session_id": str(session_id),
        "created_at": actual_created_at.isoformat(),
        "active": not soft,
        "mcp": mcp,
        "generated": True,
    }
    await write_back_row(
        redis,
        "call_uploads",
        row_id,
        fresh_row,
        score_ms=int(actual_created_at.timestamp() * 1000),
    )
    # Parent call's cached upload_id/file_path/mime_type are now stale.
    await invalidate_row(redis, "calls", call_id)

    return CreateCallUploadResponse(id=row_id)
