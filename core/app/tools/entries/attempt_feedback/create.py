"""Entry CREATE — reusable data-access layer."""

from datetime import datetime
from uuid import UUID

import asyncpg
from redis.asyncio import Redis

from app.tools.entries.attempt_feedback.types import (
    CreateAttemptFeedbackResponse,
)
from app.utils.cache.hedged_row import write_back_row


async def create_attempt_feedback(
    conn: asyncpg.Connection,
    redis: Redis,
    grade_id: UUID,
    session_id: UUID,
    total: int,
    id: UUID | None = None,
    feedback: str = "No feedback provided",
    standard_ids: list[UUID] | None = None,
    mcp: bool = False,
    soft: bool = False,
    created_at: datetime | None = None,
) -> CreateAttemptFeedbackResponse:
    """Create an attempt_feedback entry.

    Score is not stored — it's derived from the linked standard's points
    via feedbacks_standards_connection.
    """
    row = await conn.fetchrow(
        """
        INSERT INTO attempt_feedback_entry (id, grade_id, session_id, total, feedback, active, mcp, generated, created_at)
        VALUES (COALESCE($7, uuidv7()), $1, $2, $3, $4, $5, $6, true, COALESCE($8, NOW()))
        RETURNING id, created_at
        """,
        grade_id,
        session_id,
        total,
        feedback,
        not soft,
        mcp,
        id,
        created_at,
    )
    if row is None:
        raise ValueError("Failed to create attempt_feedback entry")
    entry_id = row["id"]
    actual_created_at = row["created_at"]

    if standard_ids:
        for standard_id in standard_ids:
            await conn.execute(
                """
                INSERT INTO feedbacks_standards_connection (feedbacks_id, standard_id)
                VALUES ($1, $2)
                """,
                entry_id,
                standard_id,
            )

    # Pattern A only: write-back a single cache row per feedback_id so
    # downstream child writes (e.g. additional feedbacks_standards_connection
    # inserts) can invalidate_row("attempt_feedback", entry_id). We do NOT
    # consume this row in get/search because the MV fans out one row per
    # linked standard via LEFT JOIN feedbacks_standards_connection — see
    # ``C infeasible`` note in the round-2 report. We emit one row with the
    # first standard_id (if any) for forward-compat with future read paths.
    first_standard = standard_ids[0] if standard_ids else None
    fresh_row = {
        "feedback_id": str(entry_id),
        "grade_id": str(grade_id),
        "standard_id": str(first_standard) if first_standard else None,
        "total": total,
        "feedback": feedback,
        "created_at": actual_created_at.isoformat() if actual_created_at else None,
        "id": str(entry_id),
    }
    if actual_created_at is not None:
        await write_back_row(
            redis,
            "attempt_feedback",
            entry_id,
            fresh_row,
            score_ms=int(actual_created_at.timestamp() * 1000),
        )

    return CreateAttemptFeedbackResponse(id=entry_id)
