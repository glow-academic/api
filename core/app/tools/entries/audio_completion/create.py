"""Entry CREATE — reusable data-access layer."""

from uuid import UUID

import asyncpg

from app.tools.entries.audio_completion.types import (
    CreateAudioCompletionResponse,
)


async def create_audio_completion(
    conn: asyncpg.Connection,
    audio_id: UUID,
    session_id: UUID,
    id: UUID | None = None,
    stop: bool = False,
    error: bool = False,
    message: str = "",
    mcp: bool = False,
    soft: bool = False,
) -> CreateAudioCompletionResponse:
    """Create a audio_completion entry."""
    entry_id = await conn.fetchval(
        """
        INSERT INTO audio_completion_entry (id, audio_id, session_id, stop, error, message, active, mcp, generated)
        VALUES (COALESCE($8, uuidv7()), $1, $2, $3, $4, $5, $6, $7, true)
        RETURNING id
        """,
        audio_id,
        session_id,
        stop,
        error,
        message,
        not soft,
        mcp,
        id,
    )
    return CreateAudioCompletionResponse(id=entry_id)
