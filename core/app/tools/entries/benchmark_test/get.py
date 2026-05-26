"""Entry get — reusable data-access layer."""

from uuid import UUID

import asyncpg
from redis.asyncio import Redis

from app.tools.entries.benchmark_test.types import (
    GetBenchmarkTestResponse,
)
from app.utils.cache.hedged_row import hedged_search

MV_NAME = "benchmark_test_mv"


async def get_benchmark_tests(
    conn: asyncpg.Connection,
    benchmark_ids: list[UUID],
    redis: Redis,
    *,
    bypass_cache: bool = False,
) -> list[GetBenchmarkTestResponse]:
    """Get benchmark_test entries by benchmark_id (with cache hedge).

    Composite-PK bridge keyed by ``(benchmark_id, test_id)`` —
    cached as ``{benchmark_id}:{test_id}``; merged with MV result.
    """
    if not benchmark_ids:
        return []
    rows = await conn.fetch(
        f"SELECT * FROM {MV_NAME} WHERE benchmark_id = ANY($1)", benchmark_ids,
    )
    mv_dicts = [
        {
            "id": f"{r['benchmark_id']}:{r['test_id']}",
            "benchmark_id": str(r["benchmark_id"]) if r["benchmark_id"] else None,
            "test_id": str(r["test_id"]) if r["test_id"] else None,
            "session_id": str(r["session_id"]) if r.get("session_id") else None,
            "created_at": r["created_at"],
            "active": r.get("active", True),
            "generated": r.get("generated", True),
            "mcp": r.get("mcp", False),
        }
        for r in rows
    ]
    benchmark_ids_str = {str(b) for b in benchmark_ids}

    def matches(row: dict) -> bool:
        return str(row.get("benchmark_id")) in benchmark_ids_str

    merged = await hedged_search(
        redis,
        "benchmark_test",
        mv_rows=mv_dicts,
        matches_filter=matches,
        limit=10000,
        offset=0,
        bypass_cache=bypass_cache,
    )
    return [GetBenchmarkTestResponse.model_validate(r) for r in merged]
