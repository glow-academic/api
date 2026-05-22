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

    # Pattern A + B: write-back ONE cache row per feedback_id, carrying the
    # full list of linked standard_ids. The MV LEFT JOINs
    # feedbacks_standards_connection so it fans out N rows per feedback
    # (one per linked standard); the cache stores the *aggregate* and the
    # GET/SEARCH paths fan it out client-side to match MV shape.
    #
    # Pattern C (search merge) is INFEASIBLE here — hedged_search dedupes
    # by id, but the MV emits multiple rows sharing the same feedback_id.
    # A cached row would silently mask MV rows for the same feedback. See
    # search.py for the explicit skip comment.
    #
    # Child writers (e.g. additional feedbacks_standards_connection inserts
    # after create) MUST call invalidate_row("attempt_feedback", feedback_id)
    # so a subsequent link mutates the parent cache row.
    standard_ids_list = [str(sid) for sid in (standard_ids or [])]
    fresh_row = {
        "feedback_id": str(entry_id),
        "grade_id": str(grade_id),
        "standard_ids": standard_ids_list,
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
