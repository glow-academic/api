"""Entry CREATE — reusable data-access layer."""

from uuid import UUID

import asyncpg

from app.tools.entries.attempt_conversation_completion.types import (
    CreateAttemptConversationCompletionResponse,
)


async def create_attempt_conversation_completion(
    conn: asyncpg.Connection,
    conversation_id: UUID,
    call_id: UUID,
    id: UUID | None = None,
    stop: bool = False,
    error: bool = False,
    message: str = "",
    mcp: bool = False,
) -> CreateAttemptConversationCompletionResponse:
    """Create an attempt_conversation_completion entry."""
    entry_id = await conn.fetchval(
        """
        INSERT INTO attempt_conversation_completion_entry (id, conversation_id, call_id, stop, error, message, active, mcp, generated)
        VALUES (COALESCE($7, uuidv7()), $1, $2, $3, $4, $5, true, $6, true)
        RETURNING id
        """,
        conversation_id,
        call_id,
        stop,
        error,
        message,
        mcp,
        id,
    )
    return CreateAttemptConversationCompletionResponse(id=entry_id)
