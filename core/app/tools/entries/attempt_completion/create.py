"""Entry CREATE — reusable data-access layer."""

from datetime import datetime
from uuid import UUID

import asyncpg
from redis.asyncio import Redis

from app.tools.entries.attempt_completion.types import (
    CreateAttemptCompletionResponse,
)
from app.utils.cache.hedged_row import invalidate_row, write_back_row


async def create_attempt_completion(
    conn: asyncpg.Connection,
    redis: Redis,
    attempt_id: UUID,
    session_id: UUID,
    id: UUID | None = None,
    stop: bool = False,
    error: bool = False,
    message: str = "",
    mcp: bool = False,
    soft: bool = False,
    created_at: datetime | None = None,
) -> CreateAttemptCompletionResponse:
    """Create a attempt_completion entry."""
    row = await conn.fetchrow(
        """
        INSERT INTO attempt_completion_entry (id, attempt_id, session_id, stop, error, message, active, mcp, generated, created_at)
        VALUES (COALESCE($8, uuidv7()), $1, $2, $3, $4, $5, $6, $7, true, COALESCE($9, NOW()))
        ON CONFLICT (attempt_id) DO NOTHING
        RETURNING id, created_at
        """,
        attempt_id,
        session_id,
        stop,
        error,
        message,
        not soft,
        mcp,
        id,
        created_at,
    )
    if row is None:
        entry_id = await conn.fetchval(
            "SELECT id FROM attempt_completion_entry WHERE attempt_id = $1",
            attempt_id,
        )
        return CreateAttemptCompletionResponse(id=entry_id)

    entry_id = row["id"]
    actual_created_at = row["created_at"]

    fresh_row = {
        "id": str(entry_id),
        "attempt_id": str(attempt_id),
        "session_id": str(session_id),
        "stop": stop,
        "error": error,
        "message": message,
        "active": not soft,
        "mcp": mcp,
        "generated": True,
        "created_at": actual_created_at.isoformat(),
    }
    await write_back_row(
        redis,
        "attempt_completion",
        entry_id,
        fresh_row,
        score_ms=int(actual_created_at.timestamp() * 1000),
    )
    # Parent attempt's MV ``is_completed`` flag flips.
    await invalidate_row(redis, "attempt", attempt_id)

    return CreateAttemptCompletionResponse(id=entry_id)
