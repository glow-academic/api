"""Call Uploads SEARCH — declarative filters."""

from uuid import UUID

import asyncpg

from app.tools.entries.call_uploads.types import GetCallUploadResponse


async def search_call_uploads(
    conn: asyncpg.Connection,
    call_ids: list[UUID] | None = None,
    upload_ids: list[UUID] | None = None,
    session_ids: list[UUID] | None = None,
    limit: int = 20,
    offset: int = 0,
) -> list[GetCallUploadResponse]:
    """Search call_uploads entries with declarative filters."""
    rows = await conn.fetch(
        """
        SELECT id, call_id, upload_id, session_id, created_at, active, mcp, generated
        FROM call_uploads_entry
        WHERE active = true
          AND ($1::uuid[] IS NULL OR call_id = ANY($1))
          AND ($2::uuid[] IS NULL OR upload_id = ANY($2))
          AND ($3::uuid[] IS NULL OR session_id = ANY($3))
        ORDER BY created_at DESC
        LIMIT $4 OFFSET $5
        """,
        call_ids,
        upload_ids,
        session_ids,
        limit,
        offset,
    )
    return [
        GetCallUploadResponse(
            id=r["id"],
            call_id=r["call_id"],
            upload_id=r["upload_id"],
            session_id=r["session_id"],
            created_at=r["created_at"],
            active=r["active"],
            mcp=r["mcp"],
            generated=r["generated"],
        )
        for r in rows
    ]
