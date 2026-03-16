"""Benchmark CREATE — reusable data-access layer."""

from uuid import UUID

import asyncpg  # type: ignore

from app.tools.entries.benchmark.types import CreateBenchmarkResponse
from app.tools.entries.sessions.create import create_session


async def create_benchmark(
    conn: asyncpg.Connection,
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
        session = await create_session(conn, mcp=mcp, soft=soft)
        session_id = session.id

    benchmark_id = await conn.fetchval(
        """
        INSERT INTO benchmark_entry (id, session_id, use_groups, dynamic, active, mcp, generated)
        VALUES (COALESCE($6, uuidv7()), $1, $2, $3, $4, $5, true)
        RETURNING id
        """,
        session_id,
        use_groups,
        dynamic,
        not soft,
        mcp,
        id,
    )

    if benchmark_id is None:
        raise ValueError("Failed to create benchmark entry")

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

    return CreateBenchmarkResponse(id=benchmark_id)
