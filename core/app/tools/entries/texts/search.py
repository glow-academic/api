"""Texts search — filtered/paginated query against texts_mv."""

from uuid import UUID

import asyncpg  # type: ignore
from redis.asyncio import Redis

from app.infra.docs.resolve_mv_source import resolve_mv_source
from app.tools.entries.texts.types import SearchTextResponse
from app.utils.cache.hedged_row import hedged_search

MV_NAME = "texts_mv"


async def search_texts(
    conn: asyncpg.Connection,
    redis: Redis,
    text_ids: list[UUID] | None = None,
    texts_ids: list[UUID] | None = None,
    limit: int = 20,
    offset: int = 0,
    bypass_mv: bool = False,
    bypass_cache: bool = False,
) -> list[SearchTextResponse]:
    """Search texts from texts_mv with declarative filters.

    ``text_id`` is the texts-ENTRY id; ``texts_id`` is the texts-RESOURCE id
    (the parent the document viewer references). The two filters mirror
    ``search_files``'s ``file_id`` (entry) vs ``files_ids`` (resource) split so
    a resource id can be resolved to its upload without raw SQL.
    """
    source = await resolve_mv_source(conn, MV_NAME, bypass_mv)

    rows = await conn.fetch(
        f"""
        SELECT texts_id, text_id, upload_id, file_path, mime_type, created_at
        FROM {source}
        WHERE ($1::uuid[] IS NULL OR text_id = ANY($1))
          AND ($2::uuid[] IS NULL OR texts_id = ANY($2))
        ORDER BY created_at DESC
        LIMIT $3 OFFSET $4
        """,
        text_ids,
        texts_ids,
        limit + offset + 1000,
        0,
    )

    mv_dicts = [
        {
            "texts_id": str(r["texts_id"]) if r["texts_id"] else None,
            "text_id": str(r["text_id"]),
            "upload_id": str(r["upload_id"]) if r["upload_id"] else None,
            "file_path": r["file_path"],
            "mime_type": r["mime_type"],
            "created_at": r["created_at"],
        }
        for r in rows
    ]

    text_ids_str = {str(x) for x in text_ids} if text_ids else None
    texts_ids_str = {str(x) for x in texts_ids} if texts_ids else None

    def matches(row: dict) -> bool:
        if text_ids_str is not None and str(row.get("text_id")) not in text_ids_str:
            return False
        if texts_ids_str is not None and str(row.get("texts_id")) not in texts_ids_str:
            return False
        return True

    merged = await hedged_search(
        redis,
        "texts",
        mv_rows=mv_dicts,
        matches_filter=matches,
        limit=limit,
        offset=offset,
        id_key="text_id",
        bypass_cache=bypass_cache,
    )
    return [SearchTextResponse.model_validate(r) for r in merged]
