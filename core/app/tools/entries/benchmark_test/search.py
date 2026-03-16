"""Benchmark test search — filtered/paginated query against benchmark_test_mv."""

from uuid import UUID

import asyncpg  # type: ignore

from app.infra.docs.resolve_mv_source import resolve_mv_source
from app.tools.entries.benchmark_test.types import GetBenchmarkTestResponse

MV_NAME = "benchmark_test_mv"


async def search_benchmark_tests(
    conn: asyncpg.Connection,
    benchmark_ids: list[UUID] | None = None,
    test_ids: list[UUID] | None = None,
    limit: int = 20,
    offset: int = 0,
    bypass_mv: bool = False,
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
        limit,
        offset,
    )

    return [GetBenchmarkTestResponse(**dict(r)) for r in rows]
