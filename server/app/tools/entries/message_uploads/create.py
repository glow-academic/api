"""Message Uploads CREATE — reusable data-access layer."""

from uuid import UUID

import asyncpg  # type: ignore

from app.tools.entries.message_uploads.types import (
    CreateMessageUploadResponse,
)


async def create_message_upload(
    conn: asyncpg.Connection,
    message_id: UUID,
    upload_id: UUID,
    session_id: UUID,
    id: UUID | None = None,
    mcp: bool = False,
    soft: bool = False,
) -> CreateMessageUploadResponse:
    """Create a message_uploads entry."""
    row_id = await conn.fetchval(
        """
        INSERT INTO message_uploads_entry (id, message_id, upload_id, session_id, active, mcp, generated)
        VALUES (COALESCE($6, uuidv7()), $1, $2, $3, $4, $5, true)
        RETURNING id
    """,
        message_id,
        upload_id,
        session_id,
        not soft,
        mcp,
        id,
    )

    if row_id is None:
        raise ValueError("Failed to create message_uploads entry")

    return CreateMessageUploadResponse(id=row_id)
