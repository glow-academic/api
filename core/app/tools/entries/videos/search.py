"""Videos search — filtered/paginated query against videos_mv."""

from uuid import UUID

import asyncpg  # type: ignore
from redis.asyncio import Redis

from app.infra.docs.resolve_mv_source import resolve_mv_source
from app.tools.entries.videos.types import SearchVideoResponse
from app.utils.cache.hedged_row import hedged_search

MV_NAME = "videos_mv"


async def search_videos(
    conn: asyncpg.Connection,
    redis: Redis,
    video_ids: list[UUID] | None = None,
    videos_ids: list[UUID] | None = None,
    limit: int = 20,
    offset: int = 0,
    bypass_mv: bool = False,
    bypass_cache: bool = False,
) -> list[SearchVideoResponse]:
    """Search videos from videos_mv with declarative filters."""
    source = await resolve_mv_source(conn, MV_NAME, bypass_mv)

    rows = await conn.fetch(
        f"""
        SELECT video_id, videos_id, upload_id, file_path, mime_type, size, length_seconds, created_at
        FROM {source}
        WHERE ($1::uuid[] IS NULL OR video_id = ANY($1))
          AND ($2::uuid[] IS NULL OR videos_id = ANY($2))
        ORDER BY created_at DESC
        LIMIT $3 OFFSET $4
        """,
        video_ids,
        videos_ids,
        limit + offset + 1000,
        0,
    )

    mv_dicts = [
        {
            "video_id": str(r["video_id"]),
            "videos_id": str(r["videos_id"]) if r["videos_id"] else None,
            "upload_id": str(r["upload_id"]) if r["upload_id"] else None,
            "file_path": r["file_path"],
            "mime_type": r["mime_type"],
            "size": r["size"],
            "length_seconds": r["length_seconds"],
            "created_at": r["created_at"],
        }
        for r in rows
    ]

    video_ids_str = {str(x) for x in video_ids} if video_ids else None
    videos_ids_str = {str(x) for x in videos_ids} if videos_ids else None

    def matches(row: dict) -> bool:
        if video_ids_str is not None and str(row.get("video_id")) not in video_ids_str:
            return False
        if videos_ids_str is not None and str(row.get("videos_id")) not in videos_ids_str:
            return False
        return True

    merged = await hedged_search(
        redis,
        "videos",
        mv_rows=mv_dicts,
        matches_filter=matches,
        limit=limit,
        offset=offset,
        id_key="video_id",
        bypass_cache=bypass_cache,
    )
    return [SearchVideoResponse.model_validate(r) for r in merged]
