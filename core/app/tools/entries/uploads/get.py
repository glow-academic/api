"""Uploads GET — reusable data-access layer."""

from uuid import UUID

import asyncpg  # type: ignore

from app.tools.entries.uploads.types import GetUploadResponse


async def get_upload(
    conn: asyncpg.Connection,
    upload_id: UUID,
) -> GetUploadResponse | None:
    """Get an uploads entry by ID."""
    row = await conn.fetchrow(
        """
        SELECT id, session_id, file_path, mime_type, size,
               created_at, active, mcp, generated
        FROM uploads_entry
        WHERE id = $1
    """,
        upload_id,
    )

    if row is None:
        return None

    return GetUploadResponse(
        id=row["id"],
        session_id=row["session_id"],
        file_path=row["file_path"],
        mime_type=row["mime_type"],
        size=row["size"],
        created_at=row["created_at"],
        active=row["active"],
        mcp=row["mcp"],
        generated=row["generated"],
    )
