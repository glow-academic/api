"""Upload completion search — filtered/paginated query against upload_completion_mv."""

from uuid import UUID

import asyncpg  # type: ignore
from redis.asyncio import Redis

from app.infra.docs.resolve_mv_source import resolve_mv_source
from app.tools.entries.upload_completion.types import (
    SearchUploadCompletionResponse,
)
from app.utils.cache.hedged_row import hedged_search

MV_NAME = "upload_completion_mv"


async def search_upload_completions(
    conn: asyncpg.Connection,
    redis: Redis,
    upload_ids: list[UUID] | None = None,
    limit: int = 20,
    offset: int = 0,
    bypass_mv: bool = False,
    bypass_cache: bool = False,
) -> list[SearchUploadCompletionResponse]:
    """Search upload_completions from upload_completion_mv with declarative filters."""
    source = await resolve_mv_source(conn, MV_NAME, bypass_mv)

    rows = await conn.fetch(
        f"""
        SELECT id, created_at, generated, mcp, active, upload_id, session_id, stop, error, message
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
            "id": str(r["id"]),
            "created_at": r["created_at"],
            "generated": r["generated"],
            "mcp": r["mcp"],
            "active": r["active"],
            "upload_id": str(r["upload_id"]) if r["upload_id"] else None,
            "session_id": str(r["session_id"]) if r["session_id"] else None,
            "stop": r["stop"],
            "error": r["error"],
            "message": r["message"],
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
        "upload_completion",
        mv_rows=mv_dicts,
        matches_filter=matches,
        limit=limit,
        offset=offset,
        bypass_cache=bypass_cache,
    )
    return [SearchUploadCompletionResponse.model_validate(r) for r in merged]
