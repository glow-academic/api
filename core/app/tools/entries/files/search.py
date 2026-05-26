"""Files search — filtered/paginated query against files_mv."""

from uuid import UUID

import asyncpg  # type: ignore
from redis.asyncio import Redis

from app.infra.docs.resolve_mv_source import resolve_mv_source
from app.tools.entries.files.types import SearchFileResponse
from app.utils.cache.hedged_row import hedged_search

MV_NAME = "files_mv"


async def search_files(
    conn: asyncpg.Connection,
    redis: Redis,
    file_ids: list[UUID] | None = None,
    files_ids: list[UUID] | None = None,
    mime_type: str | None = None,
    limit: int = 20,
    offset: int = 0,
    bypass_mv: bool = False,
    bypass_cache: bool = False,
) -> list[SearchFileResponse]:
    """Search files from files_mv with declarative filters."""
    source = await resolve_mv_source(conn, MV_NAME, bypass_mv)

    rows = await conn.fetch(
        f"""
        SELECT file_id, files_id, upload_id, file_path, mime_type, size, created_at
        FROM {source}
        WHERE ($1::uuid[] IS NULL OR file_id = ANY($1))
          AND ($2::uuid[] IS NULL OR files_id = ANY($2))
          AND ($3::text IS NULL OR mime_type = $3)
        ORDER BY created_at DESC
        LIMIT $4 OFFSET $5
        """,
        file_ids,
        files_ids,
        mime_type,
        limit + offset + 1000,
        0,
    )

    mv_dicts = [
        {
            "file_id": str(r["file_id"]),
            "files_id": str(r["files_id"]) if r["files_id"] else None,
            "upload_id": str(r["upload_id"]) if r["upload_id"] else None,
            "file_path": r["file_path"],
            "mime_type": r["mime_type"],
            "size": r["size"],
            "created_at": r["created_at"],
        }
        for r in rows
    ]

    file_ids_str = {str(x) for x in file_ids} if file_ids else None
    files_ids_str = {str(x) for x in files_ids} if files_ids else None

    def matches(row: dict) -> bool:
        if file_ids_str is not None and str(row.get("file_id")) not in file_ids_str:
            return False
        if files_ids_str is not None and str(row.get("files_id")) not in files_ids_str:
            return False
        if mime_type is not None and row.get("mime_type") != mime_type:
            return False
        return True

    merged = await hedged_search(
        redis,
        "files",
        mv_rows=mv_dicts,
        matches_filter=matches,
        limit=limit,
        offset=offset,
        id_key="file_id",
        bypass_cache=bypass_cache,
    )
    return [SearchFileResponse.model_validate(r) for r in merged]
