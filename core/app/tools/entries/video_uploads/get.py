"""Video Uploads GET — reusable data-access layer."""

from uuid import UUID

import asyncpg  # type: ignore

from app.tools.entries.video_uploads.types import GetVideoUploadResponse


async def get_video_upload(
    conn: asyncpg.Connection,
    video_upload_id: UUID,
) -> GetVideoUploadResponse | None:
    """Get a video_uploads entry by ID."""
    row = await conn.fetchrow(
        """
        SELECT id, video_id, upload_id, session_id,
               created_at, active, mcp, generated
        FROM video_uploads_entry
        WHERE id = $1
    """,
        video_upload_id,
    )

    if row is None:
        return None

    return GetVideoUploadResponse(
        id=row["id"],
        video_id=row["video_id"],
        upload_id=row["upload_id"],
        session_id=row["session_id"],
        created_at=row["created_at"],
        active=row["active"],
        mcp=row["mcp"],
        generated=row["generated"],
    )
