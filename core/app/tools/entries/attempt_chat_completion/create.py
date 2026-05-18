"""Entry CREATE — reusable data-access layer."""

from datetime import datetime
from uuid import UUID

import asyncpg

from app.tools.entries.attempt_chat_completion.types import (
    CreateAttemptChatCompletionResponse,
)


async def create_attempt_chat_completion(
    conn: asyncpg.Connection,
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
    entry_id = await conn.fetchval(
        """
        INSERT INTO attempt_chat_completion_entry (id, chat_id, session_id, stop, error, message, active, mcp, generated, created_at)
        VALUES (COALESCE($8, uuidv7()), $1, $2, $3, $4, $5, $6, $7, true, COALESCE($9, NOW()))
        ON CONFLICT (chat_id) DO NOTHING
        RETURNING id
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
    if entry_id is None:
        entry_id = await conn.fetchval(
            "SELECT id FROM attempt_chat_completion_entry WHERE chat_id = $1",
            chat_id,
        )
    return CreateAttemptChatCompletionResponse(id=entry_id)
