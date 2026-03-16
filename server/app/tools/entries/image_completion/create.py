"""Entry CREATE — reusable data-access layer."""

from uuid import UUID

import asyncpg

from app.tools.entries.image_completion.types import (
    CreateImageCompletionResponse,
)


async def create_image_completion(
    conn: asyncpg.Connection,
    image_id: UUID,
    session_id: UUID,
    id: UUID | None = None,
    stop: bool = False,
    error: bool = False,
    message: str = "",
    mcp: bool = False,
    soft: bool = False,
) -> CreateImageCompletionResponse:
    """Create a image_completion entry."""
    entry_id = await conn.fetchval(
        """
        INSERT INTO image_completion_entry (id, image_id, session_id, stop, error, message, active, mcp, generated)
        VALUES (COALESCE($8, uuidv7()), $1, $2, $3, $4, $5, $6, $7, true)
        RETURNING id
        """,
        image_id,
        session_id,
        stop,
        error,
        message,
        not soft,
        mcp,
        id,
    )
    return CreateImageCompletionResponse(id=entry_id)
