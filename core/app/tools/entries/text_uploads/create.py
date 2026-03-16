"""Text Uploads CREATE — reusable data-access layer."""

from uuid import UUID

import asyncpg  # type: ignore

from app.tools.entries.text_uploads.types import CreateTextUploadResponse


async def create_text_upload(
    conn: asyncpg.Connection,
    text_id: UUID,
    upload_id: UUID,
    session_id: UUID,
    *,
    id: UUID | None = None,
    mcp: bool = False,
    soft: bool = False,
) -> CreateTextUploadResponse:
    """Create a text_uploads entry."""
    row_id = await conn.fetchval(
        """
        INSERT INTO text_uploads_entry (id, text_id, upload_id, session_id, active, mcp, generated)
        VALUES (COALESCE($6, uuidv7()), $1, $2, $3, $4, $5, true)
        RETURNING id
    """,
        text_id,
        upload_id,
        session_id,
        not soft,
        mcp,
        id,
    )

    if row_id is None:
        raise ValueError("Failed to create text_uploads entry")

    return CreateTextUploadResponse(id=row_id)
