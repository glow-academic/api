"""Audios CREATE — reusable data-access layer."""

from uuid import UUID

import asyncpg  # type: ignore

from app.tools.entries.audios.types import CreateAudioResponse


async def create_audio(
    conn: asyncpg.Connection,
    session_id: UUID,
    id: UUID | None = None,
    audios_id: UUID | None = None,
    length_seconds: int = 0,
    mcp: bool = False,
    soft: bool = False,
) -> CreateAudioResponse:
    """Create an audios entry, optionally linked to an audios_resource.

    Mirrors ``tools/entries/images/create.py`` — when ``audios_id`` is
    provided, also inserts a row into ``audios_audios_connection`` so the
    entry is promoted to a library asset reference.
    """
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

    if audios_id is not None:
        await conn.execute(
            """
            INSERT INTO audios_audios_connection (audio_id, audios_id, mcp)
            VALUES ($1, $2, $3)
            """,
            audio_id,
            audios_id,
            mcp,
        )

    return CreateAudioResponse(id=audio_id)
