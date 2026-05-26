"""Entry CREATE — reusable data-access layer."""

from uuid import UUID

import asyncpg
from redis.asyncio import Redis

from app.tools.entries.text_completion.types import (
    CreateTextCompletionResponse,
)
from app.utils.cache.hedged_row import write_back_row


async def create_text_completion(
    conn: asyncpg.Connection,
    redis: Redis,
    text_id: UUID,
    session_id: UUID,
    *,
    id: UUID | None = None,
    stop: bool = False,
    error: bool = False,
    message: str = "",
    mcp: bool = False,
    soft: bool = False,
) -> CreateTextCompletionResponse:
    """Create a text_completion entry."""
    row = await conn.fetchrow(
        """
        INSERT INTO text_completion_entry (id, text_id, session_id, stop, error, message, active, mcp, generated)
        VALUES (COALESCE($8, uuidv7()), $1, $2, $3, $4, $5, $6, $7, true)
        RETURNING id, created_at
        """,
        text_id,
        session_id,
        stop,
        error,
        message,
        not soft,
        mcp,
        id,
    )
    if row is None:
        raise ValueError("Failed to create text_completion entry")

    entry_id = row["id"]
    actual_created_at = row["created_at"]

    fresh_row = {
        "id": str(entry_id),
        "text_id": str(text_id),
        "session_id": str(session_id),
        "created_at": actual_created_at.isoformat(),
        "active": not soft,
        "mcp": mcp,
        "generated": True,
        "stop": stop,
        "error": error,
        "message": message,
    }
    await write_back_row(
        redis,
        "text_completion",
        entry_id,
        fresh_row,
        score_ms=int(actual_created_at.timestamp() * 1000),
    )

    return CreateTextCompletionResponse(id=entry_id)
