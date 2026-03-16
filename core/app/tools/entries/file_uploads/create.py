"""File Uploads CREATE — reusable data-access layer."""

from uuid import UUID

import asyncpg  # type: ignore

from app.tools.entries.file_uploads.types import CreateFileUploadResponse


async def create_file_upload(
    conn: asyncpg.Connection,
    file_id: UUID,
    upload_id: UUID,
    session_id: UUID,
    id: UUID | None = None,
    mcp: bool = False,
    soft: bool = False,
) -> CreateFileUploadResponse:
    """Create a file_uploads entry."""
    row_id = await conn.fetchval(
        """
        INSERT INTO file_uploads_entry (id, file_id, upload_id, session_id, active, mcp, generated)
        VALUES (COALESCE($6, uuidv7()), $1, $2, $3, $4, $5, true)
        RETURNING id
    """,
        file_id,
        upload_id,
        session_id,
        not soft,
        mcp,
        id,
    )

    if row_id is None:
        raise ValueError("Failed to create file_uploads entry")

    return CreateFileUploadResponse(id=row_id)
