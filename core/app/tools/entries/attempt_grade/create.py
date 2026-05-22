"""Entry CREATE — reusable data-access layer."""

from datetime import datetime
from uuid import UUID

import asyncpg  # type: ignore
from redis.asyncio import Redis

from app.tools.entries.attempt_grade.types import CreateAttemptGradeResponse
from app.utils.cache.hedged_row import write_back_row


async def create_attempt_grade(
    conn: asyncpg.Connection,
    redis: Redis,
    chat_id: UUID,
    session_id: UUID,
    time_taken: int,
    passed: bool,
    score: int,
    id: UUID | None = None,
    rubric_ids: list[UUID] | None = None,
    mcp: bool = False,
    soft: bool = False,
    created_at: datetime | None = None,
) -> CreateAttemptGradeResponse:
    """Create an attempt_grade entry."""
    row = await conn.fetchrow(
        """
        INSERT INTO attempt_grade_entry
            (id, chat_id, session_id, time_taken, passed, score, active, mcp, generated, created_at)
        VALUES (COALESCE($8, uuidv7()), $1, $2, $3, $4, $5, $6, $7, true, COALESCE($9, NOW()))
        RETURNING id, created_at
        """,
        chat_id,
        session_id,
        time_taken,
        passed,
        score,
        not soft,
        mcp,
        id,
        created_at,
    )
    if row is None:
        raise ValueError("Failed to create attempt_grade entry")
    entry_id = row["id"]
    actual_created_at = row["created_at"]

    if rubric_ids:
        for rubric_id in rubric_ids:
            await conn.execute(
                """
                INSERT INTO attempt_grade_rubrics_connection
                    (grade_id, rubrics_id, generated)
                VALUES ($1, $2, true)
                """,
                entry_id,
                rubric_id,
            )

    # Write-back cache row matching get/search MV shape. The MV uses
    # DISTINCT ON (chat_id) ORDER BY created_at DESC, so the latest grade
    # for a chat_id wins — and *this* freshly-inserted row IS the latest
    # for chat_id by definition. ``total_points``/``pass_points`` derive
    # from rubric joins; default to None until the MV refreshes. ``rubric_id``
    # picks the first linked rubric_id when present.
    # FLAG: any *subsequent* attempt_grade insert for the same chat_id
    # should invalidate the prior cache row (so DISTINCT ON semantics hold
    # on the read side). That child-create-as-supersede flow isn't wired
    # here — needs follow-up: ``invalidate_row(redis, "attempt_grade",
    # <prev_grade_id>)`` before write_back_row of the new one.
    fresh_row = {
        "grade_id": str(entry_id),
        "chat_id": str(chat_id),
        "score": float(score),
        "passed": passed,
        "time_taken": time_taken,
        "total_points": None,
        "pass_points": None,
        "rubric_id": str(rubric_ids[0]) if rubric_ids else None,
        "created_at": actual_created_at.isoformat() if actual_created_at else None,
        "id": str(entry_id),
    }
    if actual_created_at is not None:
        await write_back_row(
            redis,
            "attempt_grade",
            entry_id,
            fresh_row,
            score_ms=int(actual_created_at.timestamp() * 1000),
        )

    return CreateAttemptGradeResponse(id=entry_id)
