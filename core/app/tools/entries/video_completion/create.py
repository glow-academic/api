"""Entry CREATE — reusable data-access layer."""

from uuid import UUID

import asyncpg

from app.tools.entries.video_completion.types import (
    CreateVideoCompletionResponse,
)


async def create_video_completion(
    conn: asyncpg.Connection,
    video_id: UUID,
    session_id: UUID,
    *,
    id: UUID | None = None,
    stop: bool = False,
    error: bool = False,
    message: str = "",
    mcp: bool = False,
    soft: bool = False,
) -> CreateVideoCompletionResponse:
    """Create a video_completion entry."""
    entry_id = await conn.fetchval(
        """
        INSERT INTO video_completion_entry (id, video_id, session_id, stop, error, message, active, mcp, generated)
        VALUES (COALESCE($8, uuidv7()), $1, $2, $3, $4, $5, $6, $7, true)
        RETURNING id
        """,
        video_id,
        session_id,
        stop,
        error,
        message,
        not soft,
        mcp,
        id,
    )
    return CreateVideoCompletionResponse(id=entry_id)
