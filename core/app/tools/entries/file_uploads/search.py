"""File Uploads SEARCH — declarative filters."""

from uuid import UUID

import asyncpg
from redis.asyncio import Redis

from app.tools.entries.file_uploads.types import GetFileUploadResponse
from app.utils.cache.hedged_row import hedged_search


async def search_file_uploads(
    conn: asyncpg.Connection,
    redis: Redis,
    file_ids: list[UUID] | None = None,
    upload_ids: list[UUID] | None = None,
    session_ids: list[UUID] | None = None,
    limit: int = 20,
    offset: int = 0,
    bypass_cache: bool = False,
) -> list[GetFileUploadResponse]:
    """Search file_uploads entries with declarative filters."""
    rows = await conn.fetch(
        """
        SELECT id, file_id, upload_id, session_id, created_at, active, mcp, generated
        FROM file_uploads_entry
        WHERE active = true
          AND ($1::uuid[] IS NULL OR file_id = ANY($1))
          AND ($2::uuid[] IS NULL OR upload_id = ANY($2))
          AND ($3::uuid[] IS NULL OR session_id = ANY($3))
        ORDER BY created_at DESC
        LIMIT $4 OFFSET $5
        """,
        file_ids,
        upload_ids,
        session_ids,
        limit + offset + 1000,
        0,
    )

    mv_dicts = [
        {
            "id": str(r["id"]),
            "file_id": str(r["file_id"]) if r["file_id"] else None,
            "upload_id": str(r["upload_id"]) if r["upload_id"] else None,
            "session_id": str(r["session_id"]) if r["session_id"] else None,
            "created_at": r["created_at"],
            "active": r["active"],
            "mcp": r["mcp"],
            "generated": r["generated"],
        }
        for r in rows
    ]

    file_ids_str = {str(x) for x in file_ids} if file_ids else None
    upload_ids_str = {str(x) for x in upload_ids} if upload_ids else None
    session_ids_str = {str(x) for x in session_ids} if session_ids else None

    def matches(row: dict) -> bool:
        if row.get("active") is not True:
            return False
        if file_ids_str is not None and str(row.get("file_id")) not in file_ids_str:
            return False
        if upload_ids_str is not None and str(row.get("upload_id")) not in upload_ids_str:
            return False
        if session_ids_str is not None and str(row.get("session_id")) not in session_ids_str:
            return False
        return True

    merged = await hedged_search(
        redis,
        "file_uploads",
        mv_rows=mv_dicts,
        matches_filter=matches,
        limit=limit,
        offset=offset,
        bypass_cache=bypass_cache,
    )
    return [GetFileUploadResponse.model_validate(r) for r in merged]
