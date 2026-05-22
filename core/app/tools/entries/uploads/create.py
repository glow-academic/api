"""Uploads CREATE — reusable data-access layer."""

from uuid import UUID

import asyncpg  # type: ignore
from redis.asyncio import Redis

from app.tools.entries.uploads.types import CreateUploadResponse
from app.utils.cache.hedged_row import write_back_row


async def create_upload(
    conn: asyncpg.Connection,
    redis: Redis,
    session_id: UUID,
    file_path: str,
    mime_type: str,
    size: int,
    *,
    id: UUID | None = None,
    mcp: bool = False,
    soft: bool = False,
) -> CreateUploadResponse:
    """Create an uploads entry."""
    row = await conn.fetchrow(
        """
        INSERT INTO uploads_entry (id, session_id, file_path, mime_type, size, active, mcp, generated)
        VALUES (COALESCE($7, uuidv7()), $1, $2, $3, $4, $5, $6, true)
        RETURNING id, created_at
    """,
        session_id,
        file_path,
        mime_type,
        size,
        not soft,
        mcp,
        id,
    )

    if row is None:
        raise ValueError("Failed to create uploads entry")

    upload_id = row["id"]
    actual_created_at = row["created_at"]

    # Cache-row-superset: GET shape uses "id"; SEARCH shape uses "upload_id".
    # Both keys point to the same UUID so a single row serves both paths.
    fresh_row = {
        "id": str(upload_id),
        "upload_id": str(upload_id),
        "session_id": str(session_id),
        "file_path": file_path,
        "mime_type": mime_type,
        "size": size,
        "created_at": actual_created_at.isoformat(),
        "active": not soft,
        "mcp": mcp,
        "generated": True,
    }
    await write_back_row(
        redis,
        "uploads",
        upload_id,
        fresh_row,
        score_ms=int(actual_created_at.timestamp() * 1000),
    )

    return CreateUploadResponse(id=upload_id)
