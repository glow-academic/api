"""Audio Uploads CREATE — reusable data-access layer."""

from uuid import UUID

import asyncpg  # type: ignore

from app.tools.entries.audio_uploads.types import CreateAudioUploadResponse


async def create_audio_upload(
    conn: asyncpg.Connection,
    audio_id: UUID,
    upload_id: UUID,
    session_id: UUID,
    id: UUID | None = None,
    mcp: bool = False,
    soft: bool = False,
) -> CreateAudioUploadResponse:
    """Create an audio_uploads entry."""
    row_id = await conn.fetchval(
        """
        INSERT INTO audio_uploads_entry (id, audio_id, upload_id, session_id, active, mcp, generated)
        VALUES (COALESCE($6, uuidv7()), $1, $2, $3, $4, $5, true)
        RETURNING id
    """,
        audio_id,
        upload_id,
        session_id,
        not soft,
        mcp,
        id,
    )

    if row_id is None:
        raise ValueError("Failed to create audio_uploads entry")

    return CreateAudioUploadResponse(id=row_id)
