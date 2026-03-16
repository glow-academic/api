"""Uploads CREATE — reusable data-access layer."""

from uuid import UUID

import asyncpg  # type: ignore

from app.tools.entries.uploads.types import CreateUploadResponse


async def create_upload(
    conn: asyncpg.Connection,
    session_id: UUID,
    file_path: str,
    mime_type: str,
    size: int,
    *,
    id: UUID | None = None,
    mcp: bool = False,
    soft: bool = False,
) -> CreateUploadResponse:
    """Create an uploads entry."""
    upload_id = await conn.fetchval(
        """
        INSERT INTO uploads_entry (id, session_id, file_path, mime_type, size, active, mcp, generated)
        VALUES (COALESCE($7, uuidv7()), $1, $2, $3, $4, $5, $6, true)
        RETURNING id
    """,
        session_id,
        file_path,
        mime_type,
        size,
        not soft,
        mcp,
        id,
    )

    if upload_id is None:
        raise ValueError("Failed to create uploads entry")

    return CreateUploadResponse(id=upload_id)
