"""Audios GET — reusable data-access layer."""

from uuid import UUID

import asyncpg  # type: ignore

from app.tools.entries.audios.types import GetAudioResponse


async def get_audio(
    conn: asyncpg.Connection,
    audio_id: UUID,
) -> GetAudioResponse | None:
    """Get an audios entry by ID."""
    row = await conn.fetchrow(
        """
        SELECT id, session_id, length_seconds, active, mcp, generated
        FROM audios_entry
        WHERE id = $1
    """,
        audio_id,
    )

    if row is None:
        return None

    return GetAudioResponse(
        id=row["id"],
        session_id=row["session_id"],
        length_seconds=row["length_seconds"],
        active=row["active"],
        mcp=row["mcp"],
        generated=row["generated"],
    )
