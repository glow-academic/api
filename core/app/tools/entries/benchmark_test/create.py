"""Benchmark test CREATE — reusable data-access layer."""

from uuid import UUID

import asyncpg  # type: ignore

from app.tools.entries.benchmark_test.types import CreateBenchmarkTestResponse


async def create_benchmark_test(
    conn: asyncpg.Connection,
    benchmark_id: UUID,
    test_id: UUID,
    session_id: UUID,
    mcp: bool = False,
    soft: bool = False,
) -> CreateBenchmarkTestResponse:
    """Create a benchmark_test_entry bridge row."""
    await conn.execute(
        """
        INSERT INTO benchmark_test_entry (benchmark_id, test_id, session_id, active, mcp, generated)
        VALUES ($1, $2, $3, $4, $5, true)
        """,
        benchmark_id,
        test_id,
        session_id,
        not soft,
        mcp,
    )

    return CreateBenchmarkTestResponse(benchmark_id=benchmark_id, test_id=test_id)
