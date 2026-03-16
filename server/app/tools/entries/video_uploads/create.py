"""Video Uploads CREATE — reusable data-access layer."""

from uuid import UUID

import asyncpg  # type: ignore

from app.tools.entries.video_uploads.types import CreateVideoUploadResponse


async def create_video_upload(
    conn: asyncpg.Connection,
    video_id: UUID,
    upload_id: UUID,
    session_id: UUID,
    *,
    id: UUID | None = None,
    mcp: bool = False,
    soft: bool = False,
) -> CreateVideoUploadResponse:
    """Create a video_uploads entry."""
    row_id = await conn.fetchval(
        """
        INSERT INTO video_uploads_entry (id, video_id, upload_id, session_id, active, mcp, generated)
        VALUES (COALESCE($6, uuidv7()), $1, $2, $3, $4, $5, true)
        RETURNING id
    """,
        video_id,
        upload_id,
        session_id,
        not soft,
        mcp,
        id,
    )

    if row_id is None:
        raise ValueError("Failed to create video_uploads entry")

    return CreateVideoUploadResponse(id=row_id)
