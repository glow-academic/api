"""Message Uploads SEARCH — declarative filters."""

from uuid import UUID

import asyncpg

from app.tools.entries.message_uploads.types import GetMessageUploadResponse


async def search_message_uploads(
    conn: asyncpg.Connection,
    message_ids: list[UUID] | None = None,
    upload_ids: list[UUID] | None = None,
    session_ids: list[UUID] | None = None,
    limit: int = 20,
    offset: int = 0,
) -> list[GetMessageUploadResponse]:
    """Search message_uploads entries with declarative filters."""
    rows = await conn.fetch(
        """
        SELECT id, message_id, upload_id, session_id, created_at, active, mcp, generated
        FROM message_uploads_entry
        WHERE active = true
          AND ($1::uuid[] IS NULL OR message_id = ANY($1))
          AND ($2::uuid[] IS NULL OR upload_id = ANY($2))
          AND ($3::uuid[] IS NULL OR session_id = ANY($3))
        ORDER BY created_at DESC
        LIMIT $4 OFFSET $5
        """,
        message_ids,
        upload_ids,
        session_ids,
        limit,
        offset,
    )
    return [
        GetMessageUploadResponse(
            id=r["id"],
            message_id=r["message_id"],
            upload_id=r["upload_id"],
            session_id=r["session_id"],
            created_at=r["created_at"],
            active=r["active"],
            mcp=r["mcp"],
            generated=r["generated"],
        )
        for r in rows
    ]
