"""Entry get — reusable data-access layer."""

from uuid import UUID

import asyncpg

from app.tools.entries.benchmark_test.types import (
    GetBenchmarkTestResponse,
)

MV_NAME = "benchmark_test_mv"


async def get_benchmark_tests(
    conn: asyncpg.Connection,
    benchmark_ids: list[UUID],
) -> list[GetBenchmarkTestResponse]:
    """Get benchmark_test entries by benchmark_id from MV."""
    if not benchmark_ids:
        return []
    rows = await conn.fetch(
        f"SELECT * FROM {MV_NAME} WHERE benchmark_id = ANY($1)", benchmark_ids
    )
    return [GetBenchmarkTestResponse(**dict(r)) for r in rows]
