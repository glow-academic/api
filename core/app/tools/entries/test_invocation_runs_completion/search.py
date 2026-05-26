"""Entry search — filtered/paginated query against test_invocation_runs_completion_mv."""

from uuid import UUID

import asyncpg
from redis.asyncio import Redis

from app.tools.entries.test_invocation_runs_completion.types import (
    GetTestInvocationRunsCompletionResponse,
)
from app.utils.cache.hedged_row import hedged_search

MV_NAME = "test_invocation_runs_completion_mv"


async def search_test_invocation_runs_completion(
    conn: asyncpg.Connection,
    redis: Redis,
    test_invocation_runs_ids: list[UUID] | None = None,
    limit: int = 20,
    offset: int = 0,
    bypass_cache: bool = False,
) -> tuple[list[GetTestInvocationRunsCompletionResponse], int]:
    """Search test_invocation_runs_completion entries with declarative filters.

    Returns (items, total_count). Note: total_count is the MV-only count
    (does not include cache-only merges), consistent with the existing
    baseline.
    """
    rows = await conn.fetch(
        f"""
        SELECT id, test_invocation_runs_id, stop, error, message, call_id,
               created_at, generated, mcp, active,
               COUNT(*) OVER() AS total_count
        FROM {MV_NAME}
        WHERE ($1::uuid[] IS NULL OR test_invocation_runs_id = ANY($1))
        ORDER BY created_at DESC
        LIMIT $2 OFFSET $3
        """,
        test_invocation_runs_ids,
        limit + offset + 1000,
        0,
    )
    total_count = rows[0]["total_count"] if rows else 0

    mv_dicts = [
        {
            "id": str(r["id"]),
            "test_invocation_runs_id": (
                str(r["test_invocation_runs_id"])
                if r["test_invocation_runs_id"]
                else None
            ),
            "stop": r["stop"],
            "error": r["error"],
            "message": r["message"],
            "call_id": str(r["call_id"]) if r["call_id"] else None,
            "created_at": r["created_at"],
            "generated": r["generated"],
            "mcp": r["mcp"],
            "active": r["active"],
        }
        for r in rows
    ]

    runs_ids_str = (
        {str(t) for t in test_invocation_runs_ids}
        if test_invocation_runs_ids
        else None
    )

    def matches(row: dict) -> bool:
        if (
            runs_ids_str is not None
            and str(row.get("test_invocation_runs_id")) not in runs_ids_str
        ):
            return False
        return True

    merged = await hedged_search(
        redis,
        "test_invocation_runs_completion",
        mv_rows=mv_dicts,
        matches_filter=matches,
        limit=limit,
        offset=offset,
        bypass_cache=bypass_cache,
    )
    items = [
        GetTestInvocationRunsCompletionResponse.model_validate(r) for r in merged
    ]
    return (items, total_count)
