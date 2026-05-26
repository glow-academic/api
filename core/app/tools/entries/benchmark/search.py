"""Benchmark search — filtered/paginated query against benchmark_mv."""

from datetime import datetime
from datetime import datetime as _dt
from uuid import UUID

import asyncpg  # type: ignore
from redis.asyncio import Redis

from app.infra.docs.resolve_mv_source import resolve_mv_source
from app.tools.entries.benchmark.types import GetBenchmarkResponse
from app.utils.cache.hedged_row import hedged_search

MV_NAME = "benchmark_mv"


async def search_benchmarks(
    conn: asyncpg.Connection,
    redis: Redis,
    department_ids: list[UUID] | None = None,
    eval_ids: list[UUID] | None = None,
    date_from: datetime | None = None,
    date_to: datetime | None = None,
    limit: int = 20,
    offset: int = 0,
    bypass_mv: bool = False,
    bypass_cache: bool = False,
) -> list[GetBenchmarkResponse]:
    """Search benchmarks from benchmark_mv with declarative filters."""
    source = await resolve_mv_source(conn, MV_NAME, bypass_mv)

    rows = await conn.fetch(
        f"""
        SELECT benchmark_id, use_groups, dynamic, eval_ids, profile_ids,
               department_ids, invocation_entry_ids, created_at, updated_at, active
        FROM {source}
        WHERE ($1::uuid[] IS NULL OR department_ids && $1)
          AND ($2::uuid[] IS NULL OR eval_ids && $2)
          AND ($3::timestamptz IS NULL OR created_at >= $3)
          AND ($4::timestamptz IS NULL OR created_at <= $4)
        ORDER BY created_at DESC
        LIMIT $5 OFFSET $6
        """,
        department_ids,
        eval_ids,
        date_from,
        date_to,
        limit + offset + 1000,
        0,
    )

    mv_dicts = [
        {
            "benchmark_id": str(r["benchmark_id"]),
            "use_groups": r["use_groups"],
            "dynamic": r["dynamic"],
            "eval_ids": [str(x) for x in (r["eval_ids"] or [])],
            "profile_ids": [str(x) for x in (r["profile_ids"] or [])],
            "department_ids": [str(x) for x in (r["department_ids"] or [])],
            "invocation_entry_ids": [str(x) for x in (r["invocation_entry_ids"] or [])],
            "created_at": r["created_at"],
            "updated_at": r["updated_at"],
            "active": r["active"],
        }
        for r in rows
    ]

    department_ids_str = {str(d) for d in department_ids} if department_ids else None
    eval_ids_str = {str(e) for e in eval_ids} if eval_ids else None

    def _parse_ts(ts: object) -> datetime | None:
        if isinstance(ts, str):
            return _dt.fromisoformat(ts)
        if isinstance(ts, datetime):
            return ts
        return None

    def matches(row: dict) -> bool:
        if department_ids_str is not None:
            row_deps = {str(x) for x in (row.get("department_ids") or [])}
            if not (row_deps & department_ids_str):
                return False
        if eval_ids_str is not None:
            row_evals = {str(x) for x in (row.get("eval_ids") or [])}
            if not (row_evals & eval_ids_str):
                return False
        ts = _parse_ts(row.get("created_at"))
        if date_from is not None and (ts is None or ts < date_from):
            return False
        if date_to is not None and (ts is None or ts > date_to):
            return False
        return True

    merged = await hedged_search(
        redis,
        "benchmark",
        mv_rows=mv_dicts,
        matches_filter=matches,
        limit=limit,
        offset=offset,
        id_key="benchmark_id",
        bypass_cache=bypass_cache,
    )
    return [GetBenchmarkResponse.model_validate(r) for r in merged]
