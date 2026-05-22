"""Uploads search — filtered/paginated query against uploads_mv."""

from uuid import UUID

import asyncpg  # type: ignore
from redis.asyncio import Redis

from app.infra.docs.resolve_mv_source import resolve_mv_source
from app.tools.entries.uploads.types import SearchUploadResponse
from app.utils.cache.hedged_row import hedged_search

MV_NAME = "uploads_mv"


async def search_uploads(
    conn: asyncpg.Connection,
    redis: Redis,
    upload_ids: list[UUID] | None = None,
    limit: int = 20,
    offset: int = 0,
    bypass_mv: bool = False,
    bypass_cache: bool = False,
) -> list[SearchUploadResponse]:
    """Search uploads from uploads_mv with declarative filters."""
    source = await resolve_mv_source(conn, MV_NAME, bypass_mv)

    rows = await conn.fetch(
        f"""
        SELECT upload_id, file_path, mime_type, size, created_at
        FROM {source}
        WHERE ($1::uuid[] IS NULL OR upload_id = ANY($1))
        ORDER BY created_at DESC
        LIMIT $2 OFFSET $3
        """,
        upload_ids,
        limit + offset + 1000,
        0,
    )

    mv_dicts = [
        {
            "upload_id": str(r["upload_id"]),
            "file_path": r["file_path"],
            "mime_type": r["mime_type"],
            "size": r["size"],
            "created_at": r["created_at"],
        }
        for r in rows
    ]

    upload_ids_str = {str(x) for x in upload_ids} if upload_ids else None

    def matches(row: dict) -> bool:
        if upload_ids_str is not None and str(row.get("upload_id")) not in upload_ids_str:
            return False
        return True

    merged = await hedged_search(
        redis,
        "uploads",
        mv_rows=mv_dicts,
        matches_filter=matches,
        limit=limit,
        offset=offset,
        id_key="upload_id",
        bypass_cache=bypass_cache,
    )
    return [SearchUploadResponse.model_validate(r) for r in merged]
