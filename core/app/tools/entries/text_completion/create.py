"""Entry CREATE — reusable data-access layer."""

from uuid import UUID

import asyncpg

from app.tools.entries.text_completion.types import (
    CreateTextCompletionResponse,
)


async def create_text_completion(
    conn: asyncpg.Connection,
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
    entry_id = await conn.fetchval(
        """
        INSERT INTO text_completion_entry (id, text_id, session_id, stop, error, message, active, mcp, generated)
        VALUES (COALESCE($8, uuidv7()), $1, $2, $3, $4, $5, $6, $7, true)
        RETURNING id
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
    return CreateTextCompletionResponse(id=entry_id)
