"""Uploads Completions CREATE — reusable data-access layer."""

from uuid import UUID

import asyncpg  # type: ignore
from redis.asyncio import Redis

from app.tools.entries.upload_completion.types import (
    CreateUploadCompletionResponse,
)
from app.utils.cache.hedged_row import write_back_row


async def create_upload_completion(
    conn: asyncpg.Connection,
    redis: Redis,
    upload_id: UUID,
    session_id: UUID,
    *,
    id: UUID | None = None,
    stop: bool = False,
    error: bool = False,
    message: str = "",
    mcp: bool = False,
) -> CreateUploadCompletionResponse:
    """Create an upload_completion entry."""
    row = await conn.fetchrow(
        """
        INSERT INTO upload_completion_entry (id, upload_id, session_id, stop, error, message, active, mcp, generated)
        VALUES (COALESCE($7, uuidv7()), $1, $2, $3, $4, $5, true, $6, true)
        RETURNING id, created_at
    """,
        upload_id,
        session_id,
        stop,
        error,
        message,
        mcp,
        id,
    )

    if row is None:
        raise ValueError("Failed to create upload_completion entry")

    completion_id = row["id"]
    actual_created_at = row["created_at"]

    fresh_row = {
        "id": str(completion_id),
        "upload_id": str(upload_id),
        "session_id": str(session_id),
        "created_at": actual_created_at.isoformat(),
        "active": True,
        "mcp": mcp,
        "generated": True,
        "stop": stop,
        "error": error,
        "message": message,
    }
    await write_back_row(
        redis,
        "upload_completion",
        completion_id,
        fresh_row,
        score_ms=int(actual_created_at.timestamp() * 1000),
    )

    return CreateUploadCompletionResponse(id=completion_id)
