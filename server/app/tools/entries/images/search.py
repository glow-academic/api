"""Images search — filtered/paginated query against images_mv."""

from uuid import UUID

import asyncpg  # type: ignore

from app.infra.docs.resolve_mv_source import resolve_mv_source
from app.tools.entries.images.types import SearchImageResponse

MV_NAME = "images_mv"


async def search_images(
    conn: asyncpg.Connection,
    image_ids: list[UUID] | None = None,
    images_ids: list[UUID] | None = None,
    quality_ids: list[UUID] | None = None,
    limit: int = 20,
    offset: int = 0,
    bypass_mv: bool = False,
) -> list[SearchImageResponse]:
    """Search images from images_mv with declarative filters."""
    source = await resolve_mv_source(conn, MV_NAME, bypass_mv)

    rows = await conn.fetch(
        f"""
        SELECT image_id, images_id, upload_id, file_path, mime_type, size,
               quality_id, created_at
        FROM {source}
        WHERE ($1::uuid[] IS NULL OR image_id = ANY($1))
          AND ($2::uuid[] IS NULL OR images_id = ANY($2))
          AND ($3::uuid[] IS NULL OR quality_id = ANY($3))
        ORDER BY created_at DESC
        LIMIT $4 OFFSET $5
        """,
        image_ids,
        images_ids,
        quality_ids,
        limit,
        offset,
    )

    return [SearchImageResponse(**dict(r)) for r in rows]
