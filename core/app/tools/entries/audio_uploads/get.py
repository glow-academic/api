"""Audio Uploads GET — reusable data-access layer."""

from uuid import UUID

import asyncpg  # type: ignore

from app.tools.entries.audio_uploads.types import GetAudioUploadResponse


async def get_audio_upload(
    conn: asyncpg.Connection,
    audio_upload_id: UUID,
) -> GetAudioUploadResponse | None:
    """Get an audio_uploads entry by ID."""
    row = await conn.fetchrow(
        """
        SELECT id, audio_id, upload_id, session_id,
               created_at, active, mcp, generated
        FROM audio_uploads_entry
        WHERE id = $1
    """,
        audio_upload_id,
    )

    if row is None:
        return None

    return GetAudioUploadResponse(
        id=row["id"],
        audio_id=row["audio_id"],
        upload_id=row["upload_id"],
        session_id=row["session_id"],
        created_at=row["created_at"],
        active=row["active"],
        mcp=row["mcp"],
        generated=row["generated"],
    )
