"""Entry CREATE — reusable data-access layer."""

from datetime import datetime
from uuid import UUID

import asyncpg
from redis.asyncio import Redis

from app.tools.entries.attempt_chat_completion.types import (
    CreateAttemptChatCompletionResponse,
)
from app.utils.cache.hedged_row import write_back_row


async def create_attempt_chat_completion(
    conn: asyncpg.Connection,
    redis: Redis,
    chat_id: UUID,
    session_id: UUID,
    id: UUID | None = None,
    stop: bool = False,
    error: bool = False,
    message: str = "",
    mcp: bool = False,
    soft: bool = False,
    created_at: datetime | None = None,
) -> CreateAttemptChatCompletionResponse:
    """Create an attempt_chat_completion entry."""
    row = await conn.fetchrow(
        """
        INSERT INTO attempt_chat_completion_entry (id, chat_id, session_id, stop, error, message, active, mcp, generated, created_at)
        VALUES (COALESCE($8, uuidv7()), $1, $2, $3, $4, $5, $6, $7, true, COALESCE($9, NOW()))
        ON CONFLICT (chat_id) DO NOTHING
        RETURNING id, created_at
        """,
        chat_id,
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
            "SELECT id FROM attempt_chat_completion_entry WHERE chat_id = $1",
            chat_id,
        )
        return CreateAttemptChatCompletionResponse(id=entry_id)

    entry_id = row["id"]
    actual_created_at = row["created_at"]

    fresh_row = {
        "id": str(entry_id),
        "chat_id": str(chat_id),
        "stop": stop,
        "error": error,
        "message": message,
        "created_at": actual_created_at.isoformat(),
        "active": not soft,
        "generated": True,
        "mcp": mcp,
        "session_id": str(session_id) if session_id is not None else None,
    }
    await write_back_row(
        redis,
        "attempt_chat_completion",
        entry_id,
        fresh_row,
        score_ms=int(actual_created_at.timestamp() * 1000),
    )

    return CreateAttemptChatCompletionResponse(id=entry_id)
