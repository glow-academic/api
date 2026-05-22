"""Entry CREATE — reusable data-access layer."""

from uuid import UUID

import asyncpg
from redis.asyncio import Redis

from app.tools.entries.file_completion.types import (
    CreateFileCompletionResponse,
)
from app.utils.cache.hedged_row import write_back_row


async def create_file_completion(
    conn: asyncpg.Connection,
    redis: Redis,
    file_id: UUID,
    session_id: UUID,
    id: UUID | None = None,
    stop: bool = False,
    error: bool = False,
    message: str = "",
    mcp: bool = False,
    soft: bool = False,
) -> CreateFileCompletionResponse:
    """Create a file_completion entry."""
    row = await conn.fetchrow(
        """
        INSERT INTO file_completion_entry (id, file_id, session_id, stop, error, message, active, mcp, generated)
        VALUES (COALESCE($8, uuidv7()), $1, $2, $3, $4, $5, $6, $7, true)
        RETURNING id, created_at
        """,
        file_id,
        session_id,
        stop,
        error,
        message,
        not soft,
        mcp,
        id,
    )

    if row is None:
        raise ValueError("Failed to create file_completion entry")

    entry_id = row["id"]
    created_at = row["created_at"]

    fresh_row = {
        "id": str(entry_id),
        "file_id": str(file_id),
        "stop": stop,
        "error": error,
        "message": message,
        "session_id": str(session_id),
        "created_at": created_at.isoformat(),
        "active": not soft,
        "generated": True,
        "mcp": mcp,
    }
    await write_back_row(
        redis,
        "file_completion",
        entry_id,
        fresh_row,
        score_ms=int(created_at.timestamp() * 1000),
    )

    return CreateFileCompletionResponse(id=entry_id)
