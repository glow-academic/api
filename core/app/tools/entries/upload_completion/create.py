"""Uploads Completions CREATE — reusable data-access layer."""

from uuid import UUID

import asyncpg  # type: ignore

from app.tools.entries.upload_completion.types import (
    CreateUploadCompletionResponse,
)


async def create_upload_completion(
    conn: asyncpg.Connection,
    upload_id: UUID,
    session_id: UUID,
    *,
    id: UUID | None = None,
    stop: bool = False,
    error: bool = False,
    message: str = "",
    mcp: bool = False,
) -> CreateUploadCompletionResponse:
    """Create an upload_completion entry."""
    completion_id = await conn.fetchval(
        """
        INSERT INTO upload_completion_entry (id, upload_id, session_id, stop, error, message, active, mcp, generated)
        VALUES (COALESCE($7, uuidv7()), $1, $2, $3, $4, $5, true, $6, true)
        RETURNING id
    """,
        upload_id,
        session_id,
        stop,
        error,
        message,
        mcp,
        id,
    )

    if completion_id is None:
        raise ValueError("Failed to create upload_completion entry")

    return CreateUploadCompletionResponse(id=completion_id)
