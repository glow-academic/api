"""Entry CREATE — reusable data-access layer."""

from uuid import UUID

import asyncpg
from redis.asyncio import Redis

from app.tools.entries.test_feedback.types import (
    CreateTestFeedbackResponse,
)
from app.utils.cache.hedged_row import write_back_row


async def create_test_feedback(
    conn: asyncpg.Connection,
    redis: Redis,
    grade_id: UUID,
    call_id: UUID,
    tool_call_id: UUID,
    total: int,
    *,
    id: UUID | None = None,
    feedback: str = "No feedback provided",
    total_points: int = 0,
    pass_points: int = 0,
    standard_ids: list[UUID] | None = None,
    mcp: bool = False,
    soft: bool = False,
) -> CreateTestFeedbackResponse:
    """Create a test_feedback entry.

    When ``standard_ids`` is provided, also writes one row per standard
    into the shared ``feedbacks_standards_connection`` table — mirrors
    ``create_attempt_feedback``. Lets the graded-view path read
    ``standard_id`` off ``test_feedback_mv`` via its LEFT JOIN.
    """
    row = await conn.fetchrow(
        """
        INSERT INTO test_feedback_entry (id, grade_id, call_id, tool_call_id, total, feedback, total_points, pass_points, active, mcp, generated)
        VALUES (COALESCE($10, uuidv7()), $1, $2, $3, $4, $5, $6, $7, $8, $9, true)
        RETURNING id, created_at
        """,
        grade_id,
        call_id,
        tool_call_id,
        total,
        feedback,
        total_points,
        pass_points,
        not soft,
        mcp,
        id,
    )
    entry_id = row["id"]
    actual_created_at = row["created_at"]

    if standard_ids:
        for standard_id in standard_ids:
            await conn.execute(
                """
                INSERT INTO feedbacks_standards_connection (feedbacks_id, standard_id)
                VALUES ($1, $2)
                ON CONFLICT (feedbacks_id, standard_id) DO NOTHING
                """,
                entry_id,
                standard_id,
            )

    # MV explodes one feedback × N standards into N rows via LEFT JOIN.
    # Cache one row per (feedback_id, standard_id) composite to match. With no
    # standards, cache a single row with standard_id=None (LEFT JOIN miss case).
    score_ms = int(actual_created_at.timestamp() * 1000)
    standards_for_cache: list[UUID | None] = list(standard_ids) if standard_ids else [None]
    for sid in standards_for_cache:
        composite_id = f"{entry_id}:{sid}" if sid is not None else f"{entry_id}:none"
        fresh_row = {
            "id": composite_id,
            "feedback_id": str(entry_id),
            "grade_id": str(grade_id),
            "call_id": str(call_id),
            "tool_call_id": str(tool_call_id),
            "standard_id": str(sid) if sid is not None else None,
            "total": total,
            "feedback": feedback,
            "total_points": total_points,
            "pass_points": pass_points,
            "created_at": actual_created_at.isoformat(),
        }
        await write_back_row(
            redis,
            "test_feedback",
            composite_id,
            fresh_row,
            score_ms=score_ms,
        )

    return CreateTestFeedbackResponse(id=entry_id)
