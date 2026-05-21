"""Entry CREATE — reusable data-access layer."""

from datetime import datetime
from uuid import UUID

import asyncpg
from redis.asyncio import Redis

from app.tools.entries.attempt_completion.types import (
    CreateAttemptCompletionResponse,
)


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
    entry_id = await conn.fetchval(
        """
        INSERT INTO attempt_completion_entry (id, attempt_id, session_id, stop, error, message, active, mcp, generated, created_at)
        VALUES (COALESCE($8, uuidv7()), $1, $2, $3, $4, $5, $6, $7, true, COALESCE($9, NOW()))
        ON CONFLICT (attempt_id) DO NOTHING
        RETURNING id
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
    if entry_id is None:
        entry_id = await conn.fetchval(
            "SELECT id FROM attempt_completion_entry WHERE attempt_id = $1",
            attempt_id,
        )
    return CreateAttemptCompletionResponse(id=entry_id)
