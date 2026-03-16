"""Text Uploads GET — reusable data-access layer."""

from uuid import UUID

import asyncpg  # type: ignore

from app.tools.entries.text_uploads.types import GetTextUploadResponse


async def get_text_upload(
    conn: asyncpg.Connection,
    text_upload_id: UUID,
) -> GetTextUploadResponse | None:
    """Get a text_uploads entry by ID."""
    row = await conn.fetchrow(
        """
        SELECT id, text_id, upload_id, session_id,
               created_at, active, mcp, generated
        FROM text_uploads_entry
        WHERE id = $1
    """,
        text_upload_id,
    )

    if row is None:
        return None

    return GetTextUploadResponse(
        id=row["id"],
        text_id=row["text_id"],
        upload_id=row["upload_id"],
        session_id=row["session_id"],
        created_at=row["created_at"],
        active=row["active"],
        mcp=row["mcp"],
        generated=row["generated"],
    )
