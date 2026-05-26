"""Benchmark CREATE — reusable data-access layer."""

from uuid import UUID

import asyncpg  # type: ignore
from redis.asyncio import Redis

from app.tools.entries.benchmark.types import CreateBenchmarkResponse
from app.tools.entries.sessions.create import create_session
from app.utils.cache.hedged_row import write_back_row


async def create_benchmark(
    conn: asyncpg.Connection,
    redis: Redis,
    id: UUID | None = None,
    session_id: UUID | None = None,
    evals_ids: list[UUID] | None = None,
    profiles_ids: list[UUID] | None = None,
    departments_ids: list[UUID] | None = None,
    use_groups: bool = False,
    dynamic: bool = False,
    mcp: bool = False,
    soft: bool = False,
) -> CreateBenchmarkResponse:
    """Create a benchmark entry with optional connection tables."""
    if session_id is None:
        session = await create_session(conn, redis, mcp=mcp, soft=soft)
        session_id = session.id

    row = await conn.fetchrow(
        """
        INSERT INTO benchmark_entry (id, session_id, use_groups, dynamic, active, mcp, generated)
        VALUES (COALESCE($6, uuidv7()), $1, $2, $3, $4, $5, true)
        RETURNING id, created_at, updated_at
        """,
        session_id,
        use_groups,
        dynamic,
        not soft,
        mcp,
        id,
    )

    if row is None:
        raise ValueError("Failed to create benchmark entry")
    benchmark_id = row["id"]
    actual_created_at = row["created_at"]
    actual_updated_at = row["updated_at"]

    for evals_id in evals_ids or []:
        await conn.execute(
            """
            INSERT INTO benchmark_evals_connection (benchmark_id, evals_id, generated)
            VALUES ($1, $2, true)
            """,
            benchmark_id,
            evals_id,
        )

    for profiles_id in profiles_ids or []:
        await conn.execute(
            """
            INSERT INTO benchmark_profiles_connection (benchmark_id, profiles_id, generated)
            VALUES ($1, $2, true)
            """,
            benchmark_id,
            profiles_id,
        )

    for departments_id in departments_ids or []:
        await conn.execute(
            """
            INSERT INTO benchmark_departments_connection (benchmark_id, departments_id, generated)
            VALUES ($1, $2, true)
            """,
            benchmark_id,
            departments_id,
        )

    fresh_row = {
        "benchmark_id": str(benchmark_id),
        "use_groups": use_groups,
        "dynamic": dynamic,
        "eval_ids": [str(x) for x in (evals_ids or [])],
        "profile_ids": [str(x) for x in (profiles_ids or [])],
        "department_ids": [str(x) for x in (departments_ids or [])],
        "invocation_entry_ids": [],
        "created_at": actual_created_at.isoformat(),
        "updated_at": actual_updated_at.isoformat(),
        "active": not soft,
    }
    await write_back_row(
        redis,
        "benchmark",
        benchmark_id,
        fresh_row,
        score_ms=int(actual_created_at.timestamp() * 1000),
    )

    return CreateBenchmarkResponse(id=benchmark_id)
