"""Uploads search — filtered/paginated query against uploads_mv."""

from uuid import UUID

import asyncpg  # type: ignore

from app.infra.docs.resolve_mv_source import resolve_mv_source
from app.tools.entries.uploads.types import SearchUploadResponse

MV_NAME = "uploads_mv"


async def search_uploads(
    conn: asyncpg.Connection,
    upload_ids: list[UUID] | None = None,
    limit: int = 20,
    offset: int = 0,
    bypass_mv: bool = False,
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
        limit,
        offset,
    )

    return [SearchUploadResponse(**dict(r)) for r in rows]
