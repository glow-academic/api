"""Images search — filtered/paginated query against images_mv."""

from uuid import UUID

import asyncpg  # type: ignore
from redis.asyncio import Redis

from app.infra.docs.resolve_mv_source import resolve_mv_source
from app.tools.entries.images.types import SearchImageResponse
from app.utils.cache.hedged_row import hedged_search

MV_NAME = "images_mv"


async def search_images(
    conn: asyncpg.Connection,
    redis: Redis,
    image_ids: list[UUID] | None = None,
    images_ids: list[UUID] | None = None,
    quality_ids: list[UUID] | None = None,
    limit: int = 20,
    offset: int = 0,
    bypass_mv: bool = False,
    bypass_cache: bool = False,
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
        limit + offset + 1000,
        0,
    )

    mv_dicts = [
        {
            "image_id": str(r["image_id"]),
            "images_id": str(r["images_id"]) if r["images_id"] else None,
            "upload_id": str(r["upload_id"]) if r["upload_id"] else None,
            "file_path": r["file_path"],
            "mime_type": r["mime_type"],
            "size": r["size"],
            "quality_id": str(r["quality_id"]) if r["quality_id"] else None,
            "created_at": r["created_at"],
        }
        for r in rows
    ]

    image_ids_str = {str(x) for x in image_ids} if image_ids else None
    images_ids_str = {str(x) for x in images_ids} if images_ids else None
    quality_ids_str = {str(x) for x in quality_ids} if quality_ids else None

    def matches(row: dict) -> bool:
        if image_ids_str is not None and str(row.get("image_id")) not in image_ids_str:
            return False
        if images_ids_str is not None and str(row.get("images_id")) not in images_ids_str:
            return False
        if quality_ids_str is not None and str(row.get("quality_id")) not in quality_ids_str:
            return False
        return True

    merged = await hedged_search(
        redis,
        "images",
        mv_rows=mv_dicts,
        matches_filter=matches,
        limit=limit,
        offset=offset,
        id_key="image_id",
        bypass_cache=bypass_cache,
    )
    return [SearchImageResponse.model_validate(r) for r in merged]
