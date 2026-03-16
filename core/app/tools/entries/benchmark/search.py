"""Benchmark search — filtered/paginated query against benchmark_mv."""

from datetime import datetime
from uuid import UUID

import asyncpg  # type: ignore

from app.infra.docs.resolve_mv_source import resolve_mv_source
from app.tools.entries.benchmark.types import GetBenchmarkResponse

MV_NAME = "benchmark_mv"


async def search_benchmarks(
    conn: asyncpg.Connection,
    department_ids: list[UUID] | None = None,
    date_from: datetime | None = None,
    date_to: datetime | None = None,
    limit: int = 20,
    offset: int = 0,
    bypass_mv: bool = False,
) -> list[GetBenchmarkResponse]:
    """Search benchmarks from benchmark_mv with declarative filters."""
    source = await resolve_mv_source(conn, MV_NAME, bypass_mv)

    rows = await conn.fetch(
        f"""
        SELECT benchmark_id, use_groups, dynamic, eval_ids, profile_ids,
               department_ids, invocation_entry_ids, created_at, updated_at, active
        FROM {source}
        WHERE ($1::uuid[] IS NULL OR department_ids && $1)
          AND ($2::timestamptz IS NULL OR created_at >= $2)
          AND ($3::timestamptz IS NULL OR created_at <= $3)
        ORDER BY created_at DESC
        LIMIT $4 OFFSET $5
        """,
        department_ids,
        date_from,
        date_to,
        limit,
        offset,
    )

    return [GetBenchmarkResponse(**dict(r)) for r in rows]
