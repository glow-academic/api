"""Entry CREATE — reusable data-access layer."""

from uuid import UUID

import asyncpg
from redis.asyncio import Redis

from app.tools.entries.attempt_conversation_completion.types import (
    CreateAttemptConversationCompletionResponse,
)
from app.utils.cache.hedged_row import write_back_row


async def create_attempt_conversation_completion(
    conn: asyncpg.Connection,
    redis: Redis,
    conversation_id: UUID,
    session_id: UUID,
    id: UUID | None = None,
    stop: bool = False,
    error: bool = False,
    message: str = "",
    mcp: bool = False,
) -> CreateAttemptConversationCompletionResponse:
    """Create an attempt_conversation_completion entry."""
    row = await conn.fetchrow(
        """
        INSERT INTO attempt_conversation_completion_entry (id, conversation_id, session_id, stop, error, message, active, mcp, generated)
        VALUES (COALESCE($7, uuidv7()), $1, $2, $3, $4, $5, true, $6, true)
        RETURNING id, created_at
        """,
        conversation_id,
        session_id,
        stop,
        error,
        message,
        mcp,
        id,
    )
    entry_id = row["id"]
    created_at = row["created_at"]

    fresh_row = {
        "id": str(entry_id),
        "created_at": created_at.isoformat(),
        "generated": True,
        "mcp": mcp,
        "active": True,
        "conversation_id": str(conversation_id),
        "stop": stop,
        "error": error,
        "message": message,
        "session_id": str(session_id) if session_id is not None else None,
    }
    await write_back_row(
        redis,
        "attempt_conversation_completion",
        entry_id,
        fresh_row,
        score_ms=int(created_at.timestamp() * 1000),
    )

    return CreateAttemptConversationCompletionResponse(id=entry_id)
