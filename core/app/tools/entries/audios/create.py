"""Audios CREATE — reusable data-access layer."""

from uuid import UUID

import asyncpg  # type: ignore
from redis.asyncio import Redis

from app.tools.entries.audios.types import CreateAudioResponse
from app.utils.cache.hedged_row import write_back_row


async def create_audio(
    conn: asyncpg.Connection,
    redis: Redis,
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
    row = await conn.fetchrow(
        """
        INSERT INTO audios_entry (id, session_id, length_seconds, active, mcp, generated)
        VALUES (COALESCE($5, uuidv7()), $1, $2, $3, $4, true)
        RETURNING id, created_at
    """,
        session_id,
        length_seconds,
        not soft,
        mcp,
        id,
    )

    if row is None:
        raise ValueError("Failed to create audios entry")

    audio_id = row["id"]
    actual_created_at = row["created_at"]

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

    # Cache-row-superset: includes BOTH GET-shape (entry columns) and
    # SEARCH-shape (audios_mv = audios_entry JOIN audios_resource) fields.
    # Upload-denormalized fields (upload_id/file_path/mime_type/size) and
    # voice_id are None until the corresponding audio_uploads row links in.
    fresh_row = {
        "id": str(audio_id),
        "audio_id": str(audio_id),
        "session_id": str(session_id),
        "length_seconds": length_seconds,
        "active": not soft,
        "mcp": mcp,
        "generated": True,
        "created_at": actual_created_at.isoformat(),
        "upload_id": None,
        "file_path": None,
        "mime_type": None,
        "size": None,
        "voice_id": None,
    }
    await write_back_row(
        redis,
        "audios",
        audio_id,
        fresh_row,
        score_ms=int(actual_created_at.timestamp() * 1000),
    )

    return CreateAudioResponse(id=audio_id)
