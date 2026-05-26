"""Benchmark test CREATE — reusable data-access layer."""

from uuid import UUID

import asyncpg  # type: ignore
from redis.asyncio import Redis

from app.tools.entries.benchmark_test.types import CreateBenchmarkTestResponse
from app.utils.cache.hedged_row import write_back_row


async def create_benchmark_test(
    conn: asyncpg.Connection,
    redis: Redis,
    benchmark_id: UUID,
    test_id: UUID,
    session_id: UUID,
    mcp: bool = False,
    soft: bool = False,
) -> CreateBenchmarkTestResponse:
    """Create a benchmark_test_entry bridge row."""
    row = await conn.fetchrow(
        """
        INSERT INTO benchmark_test_entry (benchmark_id, test_id, session_id, active, mcp, generated)
        VALUES ($1, $2, $3, $4, $5, true)
        RETURNING created_at
        """,
        benchmark_id,
        test_id,
        session_id,
        not soft,
        mcp,
    )
    actual_created_at = row["created_at"] if row else None

    composite_id = f"{benchmark_id}:{test_id}"
    fresh_row = {
        "id": composite_id,
        "benchmark_id": str(benchmark_id),
        "test_id": str(test_id),
        "created_at": actual_created_at.isoformat() if actual_created_at else None,
        "active": not soft,
        "generated": True,
        "mcp": mcp,
        "session_id": str(session_id),
    }
    if actual_created_at is not None:
        await write_back_row(
            redis,
            "benchmark_test",
            composite_id,
            fresh_row,
            score_ms=int(actual_created_at.timestamp() * 1000),
        )

    return CreateBenchmarkTestResponse(benchmark_id=benchmark_id, test_id=test_id)
