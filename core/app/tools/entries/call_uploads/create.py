"""Call Uploads CREATE — reusable data-access layer."""

from uuid import UUID

import asyncpg  # type: ignore

from app.tools.entries.call_uploads.types import CreateCallUploadResponse


async def create_call_upload(
    conn: asyncpg.Connection,
    call_id: UUID,
    upload_id: UUID,
    session_id: UUID,
    id: UUID | None = None,
    mcp: bool = False,
    soft: bool = False,
) -> CreateCallUploadResponse:
    """Create a call_uploads entry."""
    row_id = await conn.fetchval(
        """
        INSERT INTO call_uploads_entry (id, call_id, upload_id, session_id, active, mcp, generated)
        VALUES (COALESCE($6, uuidv7()), $1, $2, $3, $4, $5, true)
        RETURNING id
    """,
        call_id,
        upload_id,
        session_id,
        not soft,
        mcp,
        id,
    )

    if row_id is None:
        raise ValueError("Failed to create call_uploads entry")

    return CreateCallUploadResponse(id=row_id)
