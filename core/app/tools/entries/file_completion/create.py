"""Entry CREATE — reusable data-access layer."""

from uuid import UUID

import asyncpg

from app.tools.entries.file_completion.types import (
    CreateFileCompletionResponse,
)


async def create_file_completion(
    conn: asyncpg.Connection,
    file_id: UUID,
    session_id: UUID,
    id: UUID | None = None,
    stop: bool = False,
    error: bool = False,
    message: str = "",
    mcp: bool = False,
    soft: bool = False,
) -> CreateFileCompletionResponse:
    """Create a file_completion entry."""
    entry_id = await conn.fetchval(
        """
        INSERT INTO file_completion_entry (id, file_id, session_id, stop, error, message, active, mcp, generated)
        VALUES (COALESCE($8, uuidv7()), $1, $2, $3, $4, $5, $6, $7, true)
        RETURNING id
        """,
        file_id,
        session_id,
        stop,
        error,
        message,
        not soft,
        mcp,
        id,
    )
    return CreateFileCompletionResponse(id=entry_id)
