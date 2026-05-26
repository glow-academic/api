"""File completion search — filtered/paginated query against file_completion_mv."""

from uuid import UUID

import asyncpg  # type: ignore
from redis.asyncio import Redis

from app.infra.docs.resolve_mv_source import resolve_mv_source
from app.tools.entries.file_completion.types import (
    GetFileCompletionResponse,
)
from app.utils.cache.hedged_row import hedged_search

MV_NAME = "file_completion_mv"


async def search_file_completions(
    conn: asyncpg.Connection,
    redis: Redis,
    file_ids: list[UUID] | None = None,
    limit: int = 20,
    offset: int = 0,
    bypass_mv: bool = False,
    bypass_cache: bool = False,
) -> list[GetFileCompletionResponse]:
    """Search file_completion entries from file_completion_mv with declarative filters."""
    source = await resolve_mv_source(conn, MV_NAME, bypass_mv)

    rows = await conn.fetch(
        f"""
        SELECT id, file_id, stop, error, message, session_id, created_at, active, generated, mcp
        FROM {source}
        WHERE ($1::uuid[] IS NULL OR file_id = ANY($1))
        ORDER BY created_at DESC
        LIMIT $2 OFFSET $3
        """,
        file_ids,
        limit + offset + 1000,
        0,
    )

    mv_dicts = [
        {
            "id": str(r["id"]),
            "file_id": str(r["file_id"]) if r["file_id"] else None,
            "stop": r["stop"],
            "error": r["error"],
            "message": r["message"],
            "session_id": str(r["session_id"]) if r["session_id"] else None,
            "created_at": r["created_at"],
            "active": r["active"],
            "generated": r["generated"],
            "mcp": r["mcp"],
        }
        for r in rows
    ]

    file_ids_str = {str(f) for f in file_ids} if file_ids else None

    def matches(row: dict) -> bool:
        if file_ids_str is not None and str(row.get("file_id")) not in file_ids_str:
            return False
        return True

    merged = await hedged_search(
        redis,
        "file_completion",
        mv_rows=mv_dicts,
        matches_filter=matches,
        limit=limit,
        offset=offset,
        bypass_cache=bypass_cache,
    )
    return [GetFileCompletionResponse.model_validate(r) for r in merged]
