"""Entry CREATE — reusable data-access layer."""

from uuid import UUID

import asyncpg

from app.tools.entries.attempt_message_completion.types import (
    CreateAttemptMessageCompletionResponse,
)


async def create_attempt_message_completion(
    conn: asyncpg.Connection,
    attempt_message_id: UUID,
    call_id: UUID,
    id: UUID | None = None,
    stop: bool = False,
    error: bool = False,
    message: str = "",
    mcp: bool = False,
    soft: bool = False,
) -> CreateAttemptMessageCompletionResponse:
    """Create a attempt_message_completion entry."""
    entry_id = await conn.fetchval(
        """
        INSERT INTO attempt_message_completion_entry (id, attempt_message_id, call_id, stop, error, message, active, mcp, generated)
        VALUES (COALESCE($8, uuidv7()), $1, $2, $3, $4, $5, $6, $7, true)
        RETURNING id
        """,
        attempt_message_id,
        call_id,
        stop,
        error,
        message,
        not soft,
        mcp,
        id,
    )
    return CreateAttemptMessageCompletionResponse(id=entry_id)
