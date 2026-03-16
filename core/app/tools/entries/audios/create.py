"""Audios CREATE — reusable data-access layer."""

from uuid import UUID

import asyncpg  # type: ignore

from app.tools.entries.audios.types import CreateAudioResponse


async def create_audio(
    conn: asyncpg.Connection,
    session_id: UUID,
    id: UUID | None = None,
    length_seconds: int = 0,
    mcp: bool = False,
    soft: bool = False,
) -> CreateAudioResponse:
    """Create an audios entry."""
    audio_id = await conn.fetchval(
        """
        INSERT INTO audios_entry (id, session_id, length_seconds, active, mcp, generated)
        VALUES (COALESCE($5, uuidv7()), $1, $2, $3, $4, true)
        RETURNING id
    """,
        session_id,
        length_seconds,
        not soft,
        mcp,
        id,
    )

    if audio_id is None:
        raise ValueError("Failed to create audios entry")

    return CreateAudioResponse(id=audio_id)
