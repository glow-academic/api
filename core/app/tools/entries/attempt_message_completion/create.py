"""Entry CREATE — reusable data-access layer."""

from uuid import UUID

import asyncpg
from redis.asyncio import Redis

from app.tools.entries.attempt_message_completion.types import (
    CreateAttemptMessageCompletionResponse,
)
from app.utils.cache.hedged_row import write_back_row


async def create_attempt_message_completion(
    conn: asyncpg.Connection,
    redis: Redis,
    attempt_message_id: UUID,
    session_id: UUID,
    id: UUID | None = None,
    stop: bool = False,
    error: bool = False,
    message: str = "",
    mcp: bool = False,
    soft: bool = False,
) -> CreateAttemptMessageCompletionResponse:
    """Create a attempt_message_completion entry."""
    row = await conn.fetchrow(
        """
        INSERT INTO attempt_message_completion_entry (id, attempt_message_id, session_id, stop, error, message, active, mcp, generated)
        VALUES (COALESCE($8, uuidv7()), $1, $2, $3, $4, $5, $6, $7, true)
        RETURNING id, created_at
        """,
        attempt_message_id,
        session_id,
        stop,
        error,
        message,
        not soft,
        mcp,
        id,
    )
    if row is None:
        raise ValueError("Failed to create attempt_message_completion entry")
    entry_id = row["id"]
    actual_created_at = row["created_at"]

    fresh_row = {
        "id": str(entry_id),
        "attempt_message_id": str(attempt_message_id),
        "stop": stop,
        "error": error,
        "message": message,
        "session_id": str(session_id),
        "created_at": actual_created_at.isoformat(),
        "active": not soft,
        "generated": True,
        "mcp": mcp,
    }
    await write_back_row(
        redis,
        "attempt_message_completion",
        entry_id,
        fresh_row,
        score_ms=int(actual_created_at.timestamp() * 1000),
    )

    return CreateAttemptMessageCompletionResponse(id=entry_id)
