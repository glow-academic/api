"""Text Uploads SEARCH — declarative filters."""

from uuid import UUID

import asyncpg

from app.tools.entries.text_uploads.types import GetTextUploadResponse


async def search_text_uploads(
    conn: asyncpg.Connection,
    text_ids: list[UUID] | None = None,
    upload_ids: list[UUID] | None = None,
    session_ids: list[UUID] | None = None,
    limit: int = 20,
    offset: int = 0,
) -> list[GetTextUploadResponse]:
    """Search text_uploads entries with declarative filters."""
    rows = await conn.fetch(
        """
        SELECT id, text_id, upload_id, session_id, created_at, active, mcp, generated
        FROM text_uploads_entry
        WHERE active = true
          AND ($1::uuid[] IS NULL OR text_id = ANY($1))
          AND ($2::uuid[] IS NULL OR upload_id = ANY($2))
          AND ($3::uuid[] IS NULL OR session_id = ANY($3))
        ORDER BY created_at DESC
        LIMIT $4 OFFSET $5
        """,
        text_ids,
        upload_ids,
        session_ids,
        limit,
        offset,
    )
    return [
        GetTextUploadResponse(
            id=r["id"],
            text_id=r["text_id"],
            upload_id=r["upload_id"],
            session_id=r["session_id"],
            created_at=r["created_at"],
            active=r["active"],
            mcp=r["mcp"],
            generated=r["generated"],
        )
        for r in rows
    ]
