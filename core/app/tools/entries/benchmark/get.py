"""Benchmark get — reusable data-access layer."""

from uuid import UUID

import asyncpg  # type: ignore
from redis.asyncio import Redis

from app.tools.entries.benchmark.types import GetBenchmarkResponse
from app.utils.cache.hedged_row import read_back_row

MV_NAME = "benchmark_mv"


async def get_benchmarks(
    conn: asyncpg.Connection,
    ids: list[UUID],
    redis: Redis,
    *,
    bypass_cache: bool = False,
) -> list[GetBenchmarkResponse]:
    """Fetch benchmark entries by IDs from the MV."""
    if not ids:
        return []

    cached_results: dict[str, GetBenchmarkResponse] = {}
    missing_ids: list[UUID] = []
    if not bypass_cache:
        for bid in ids:
            cached = await read_back_row(redis, "benchmark", bid)
            if cached is not None:
                cached_results[str(bid)] = GetBenchmarkResponse.model_validate(cached)
            else:
                missing_ids.append(bid)
    else:
        missing_ids = list(ids)

    mv_results: dict[str, GetBenchmarkResponse] = {}
    if missing_ids:
        rows = await conn.fetch(
            f"""
            SELECT
                benchmark_id, use_groups, dynamic,
                eval_ids, profile_ids, department_ids,
                invocation_entry_ids, created_at, updated_at, active
            FROM {MV_NAME}
            WHERE benchmark_id = ANY($1)
            """,
            missing_ids,
        )

        for r in rows:
            mv_results[str(r["benchmark_id"])] = GetBenchmarkResponse(
                benchmark_id=r["benchmark_id"],
                use_groups=r["use_groups"],
                dynamic=r["dynamic"],
                eval_ids=r["eval_ids"],
                profile_ids=r["profile_ids"],
                department_ids=r["department_ids"],
                invocation_entry_ids=r["invocation_entry_ids"],
                created_at=r["created_at"],
                updated_at=r["updated_at"],
                active=r["active"],
            )

    out: list[GetBenchmarkResponse] = []
    for bid in ids:
        key = str(bid)
        if key in cached_results:
            out.append(cached_results[key])
        elif key in mv_results:
            out.append(mv_results[key])
    return out
