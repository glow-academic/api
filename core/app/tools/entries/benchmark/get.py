"""Benchmark get — reusable data-access layer."""

from uuid import UUID

import asyncpg  # type: ignore

from app.tools.entries.benchmark.types import GetBenchmarkResponse

MV_NAME = "benchmark_mv"


async def get_benchmarks(
    conn: asyncpg.Connection,
    ids: list[UUID],
) -> list[GetBenchmarkResponse]:
    """Fetch benchmark entries by IDs from the MV."""
    if not ids:
        return []

    rows = await conn.fetch(
        f"""
        SELECT
            benchmark_id, use_groups, dynamic,
            eval_ids, profile_ids, department_ids,
            invocation_entry_ids, created_at, updated_at, active
        FROM {MV_NAME}
        WHERE benchmark_id = ANY($1)
        """,
        ids,
    )

    return [
        GetBenchmarkResponse(
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
        for r in rows
    ]
