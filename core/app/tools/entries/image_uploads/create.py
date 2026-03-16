"""Image Uploads CREATE — reusable data-access layer."""

from uuid import UUID

import asyncpg  # type: ignore

from app.tools.entries.image_uploads.types import CreateImageUploadResponse


async def create_image_upload(
    conn: asyncpg.Connection,
    image_id: UUID,
    upload_id: UUID,
    session_id: UUID,
    id: UUID | None = None,
    mcp: bool = False,
    soft: bool = False,
) -> CreateImageUploadResponse:
    """Create an image_uploads entry."""
    row_id = await conn.fetchval(
        """
        INSERT INTO image_uploads_entry (id, image_id, upload_id, session_id, active, mcp, generated)
        VALUES (COALESCE($6, uuidv7()), $1, $2, $3, $4, $5, true)
        RETURNING id
    """,
        image_id,
        upload_id,
        session_id,
        not soft,
        mcp,
        id,
    )

    if row_id is None:
        raise ValueError("Failed to create image_uploads entry")

    return CreateImageUploadResponse(id=row_id)
