"""Entry search — filtered/paginated query against test_invocation_traces_mv."""

from datetime import datetime as _dt
from uuid import UUID

import asyncpg
from redis.asyncio import Redis

from app.tools.entries.test_invocation_traces.types import (
    GetTestInvocationTracesResponse,
)
from app.utils.cache.hedged_row import hedged_search_with_total

MV_NAME = "test_invocation_traces_mv"


async def search_test_invocation_traces(
    conn: asyncpg.Connection,
    redis: Redis,
    test_invocation_ids: list[UUID] | None = None,
    limit: int = 20,
    offset: int = 0,
    bypass_cache: bool = False,
) -> tuple[list[GetTestInvocationTracesResponse], int]:
    """Search test_invocation_traces from test_invocation_traces_mv with declarative filters.

    Returns (items, total_count).
    """
    # Padded fetch so dedupe against the cache merge still leaves enough rows
    # to satisfy offset+limit. COUNT(*) OVER() reflects the unpaginated total.
    rows = await conn.fetch(
        f"""
        SELECT id, test_invocation_id, run_id, created_at, updated_at,
               generated, mcp, active,
               reasoning_level_ids, temperature_level_ids, voice_ids,
               prompt_ids, instruction_ids, tool_ids, quality_ids, modality_ids,
               COUNT(*) OVER() AS total_count
        FROM {MV_NAME}
        WHERE ($1::uuid[] IS NULL OR test_invocation_id = ANY($1))
        ORDER BY created_at DESC
        LIMIT $2 OFFSET $3
        """,
        test_invocation_ids,
        limit + offset + 1000,
        0,
    )

    mv_total = rows[0]["total_count"] if rows else 0

    mv_dicts = [
        {k: v for k, v in dict(r).items() if k != "total_count"} for r in rows
    ]

    inv_ids_str = (
        {str(x) for x in test_invocation_ids} if test_invocation_ids else None
    )

    def matches(row: dict) -> bool:
        if (
            inv_ids_str is not None
            and str(row.get("test_invocation_id")) not in inv_ids_str
        ):
            return False
        return True

    def _sort_key(row: dict) -> _dt:
        ts = row.get("created_at")
        if ts is None:
            return _dt.min
        if isinstance(ts, str):
            return _dt.fromisoformat(ts)
        return ts

    items, total = await hedged_search_with_total(
        redis,
        "test_invocation_traces",
        mv_rows=mv_dicts,
        mv_total=mv_total,
        matches_filter=matches,
        sort_key=_sort_key,
        limit=limit,
        offset=offset,
        id_key="id",
        bypass_cache=bypass_cache,
    )

    return (
        [GetTestInvocationTracesResponse.model_validate(r) for r in items],
        total,
    )
