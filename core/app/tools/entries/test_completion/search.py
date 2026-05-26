"""Test completion search — filtered/paginated query against test_completion_mv."""

from uuid import UUID

import asyncpg  # type: ignore
from redis.asyncio import Redis

from app.infra.docs.resolve_mv_source import resolve_mv_source
from app.tools.entries.test_completion.types import (
    GetTestCompletionResponse,
)
from app.utils.cache.hedged_row import hedged_search

MV_NAME = "test_completion_mv"


async def search_test_completions(
    conn: asyncpg.Connection,
    redis: Redis,
    test_ids: list[UUID] | None = None,
    limit: int = 20,
    offset: int = 0,
    bypass_mv: bool = False,
    bypass_cache: bool = False,
) -> list[GetTestCompletionResponse]:
    """Search test_completion entries from test_completion_mv with declarative filters."""
    source = await resolve_mv_source(conn, MV_NAME, bypass_mv)

    rows = await conn.fetch(
        f"""
        SELECT id, test_id, stop, error, message, call_id, created_at, active, generated, mcp
        FROM {source}
        WHERE ($1::uuid[] IS NULL OR test_id = ANY($1))
        ORDER BY created_at DESC
        LIMIT $2 OFFSET $3
        """,
        test_ids,
        limit + offset + 1000,
        0,
    )

    mv_dicts = [
        {
            "id": str(r["id"]),
            "test_id": str(r["test_id"]) if r["test_id"] else None,
            "stop": r["stop"],
            "error": r["error"],
            "message": r["message"],
            "call_id": str(r["call_id"]) if r["call_id"] else None,
            "created_at": r["created_at"],
            "active": r["active"],
            "generated": r["generated"],
            "mcp": r["mcp"],
        }
        for r in rows
    ]

    test_ids_str = {str(t) for t in test_ids} if test_ids else None

    def matches(row: dict) -> bool:
        if test_ids_str is not None and str(row.get("test_id")) not in test_ids_str:
            return False
        return True

    merged = await hedged_search(
        redis,
        "test_completion",
        mv_rows=mv_dicts,
        matches_filter=matches,
        limit=limit,
        offset=offset,
        bypass_cache=bypass_cache,
    )
    return [GetTestCompletionResponse.model_validate(r) for r in merged]
