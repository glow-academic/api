"""Benchmark test search — filtered/paginated query against benchmark_test_mv."""

from uuid import UUID

import asyncpg  # type: ignore
from redis.asyncio import Redis

from app.infra.docs.resolve_mv_source import resolve_mv_source
from app.tools.entries.benchmark_test.types import GetBenchmarkTestResponse
from app.utils.cache.hedged_row import hedged_search

MV_NAME = "benchmark_test_mv"


async def search_benchmark_tests(
    conn: asyncpg.Connection,
    redis: Redis,
    benchmark_ids: list[UUID] | None = None,
    test_ids: list[UUID] | None = None,
    limit: int = 20,
    offset: int = 0,
    bypass_mv: bool = False,
    bypass_cache: bool = False,
) -> list[GetBenchmarkTestResponse]:
    """Search benchmark_test entries from benchmark_test_mv with declarative filters."""
    source = await resolve_mv_source(conn, MV_NAME, bypass_mv)

    rows = await conn.fetch(
        f"""
        SELECT benchmark_id, test_id, created_at, active, generated, mcp, session_id
        FROM {source}
        WHERE ($1::uuid[] IS NULL OR benchmark_id = ANY($1))
          AND ($2::uuid[] IS NULL OR test_id = ANY($2))
        ORDER BY created_at DESC
        LIMIT $3 OFFSET $4
        """,
        benchmark_ids,
        test_ids,
        limit + offset + 1000,
        0,
    )

    mv_dicts = [
        {
            "id": f"{r['benchmark_id']}:{r['test_id']}",
            "benchmark_id": str(r["benchmark_id"]),
            "test_id": str(r["test_id"]),
            "created_at": r["created_at"],
            "active": r["active"],
            "generated": r["generated"],
            "mcp": r["mcp"],
            "session_id": str(r["session_id"]) if r["session_id"] else None,
        }
        for r in rows
    ]

    benchmark_ids_str = {str(b) for b in benchmark_ids} if benchmark_ids else None
    test_ids_str = {str(t) for t in test_ids} if test_ids else None

    def matches(row: dict) -> bool:
        if benchmark_ids_str is not None and str(row.get("benchmark_id")) not in benchmark_ids_str:
            return False
        if test_ids_str is not None and str(row.get("test_id")) not in test_ids_str:
            return False
        if not row.get("active", True):
            return False
        return True

    merged = await hedged_search(
        redis,
        "benchmark_test",
        mv_rows=mv_dicts,
        matches_filter=matches,
        limit=limit,
        offset=offset,
        bypass_cache=bypass_cache,
    )
    return [
        GetBenchmarkTestResponse.model_validate({k: v for k, v in r.items() if k != "id"})
        for r in merged
    ]
