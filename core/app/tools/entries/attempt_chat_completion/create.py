"""Entry CREATE — reusable data-access layer."""

from uuid import UUID

import asyncpg

from app.tools.entries.attempt_chat_completion.types import (
    CreateAttemptChatCompletionResponse,
)


async def create_attempt_chat_completion(
    conn: asyncpg.Connection,
    chat_id: UUID,
    call_id: UUID,
    id: UUID | None = None,
    stop: bool = False,
    error: bool = False,
    message: str = "",
    mcp: bool = False,
    soft: bool = False,
) -> CreateAttemptChatCompletionResponse:
    """Create an attempt_chat_completion entry."""
    entry_id = await conn.fetchval(
        """
        INSERT INTO attempt_chat_completion_entry (id, chat_id, call_id, stop, error, message, active, mcp, generated)
        VALUES (COALESCE($8, uuidv7()), $1, $2, $3, $4, $5, $6, $7, true)
        RETURNING id
        """,
        chat_id,
        call_id,
        stop,
        error,
        message,
        not soft,
        mcp,
        id,
    )
    return CreateAttemptChatCompletionResponse(id=entry_id)
