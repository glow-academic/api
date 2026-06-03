"""Entry CREATE — reusable data-access layer."""

from uuid import UUID

import asyncpg  # type: ignore
from redis.asyncio import Redis

from app.tools.entries.test_grade.types import CreateTestGradeResponse
from app.utils.cache.hedged_row import invalidate_row, write_back_row


async def create_test_grade(
    conn: asyncpg.Connection,
    redis: Redis,
    invocation_id: UUID,
    call_id: UUID,
    time_taken: int,
    passed: bool,
    score: int,
    *,
    id: UUID | None = None,
    mcp: bool = False,
    soft: bool = False,
) -> CreateTestGradeResponse:
    """Create a test_grade entry."""
    row = await conn.fetchrow(
        """
        INSERT INTO test_grade_entry
            (id, invocation_id, call_id, time_taken, passed, score, active, mcp, generated)
        VALUES (COALESCE($8, uuidv7()), $1, $2, $3, $4, $5, $6, $7, true)
        RETURNING id, created_at, updated_at
        """,
        invocation_id,
        call_id,
        time_taken,
        passed,
        score,
        not soft,
        mcp,
        id,
    )

    if row is None:
        raise ValueError("Failed to create test_grade entry")

    entry_id = row["id"]
    created_at = row["created_at"]
    updated_at = row["updated_at"]

    fresh_row = {
        "id": str(entry_id),
        "invocation_id": str(invocation_id),
        "created_at": created_at.isoformat(),
        "updated_at": updated_at.isoformat() if updated_at else created_at.isoformat(),
        "passed": passed,
        "score": score,
        "time_taken": time_taken,
        "generated": True,
        "mcp": mcp,
        "active": not soft,
        "call_id": str(call_id),
    }
    await write_back_row(
        redis,
        "test_grade",
        entry_id,
        fresh_row,
        score_ms=int(created_at.timestamp() * 1000),
    )
    # Bust the parent test_invocation write-back row: the MV derives
    # ``grade_id``/``grade_score``/``grade_passed``/``grade_time_taken`` and
    # ``invocation_completed`` from the latest test_grade. The parent's cached
    # row was written grade=None / completed=False at create-time; without this
    # a cached parent GET shadows the hydrated MV until TTL (#98 sibling).
    await invalidate_row(redis, "test_invocation", invocation_id)

    return CreateTestGradeResponse(id=entry_id)
