"""Entry CREATE — reusable data-access layer."""

from uuid import UUID

import asyncpg

from app.tools.entries.attempt_feedback.types import (
    CreateAttemptFeedbackResponse,
)


async def create_attempt_feedback(
    conn: asyncpg.Connection,
    grade_id: UUID,
    call_id: UUID,
    total: int,
    id: UUID | None = None,
    feedback: str = "No feedback provided",
    standard_ids: list[UUID] | None = None,
    mcp: bool = False,
    soft: bool = False,
) -> CreateAttemptFeedbackResponse:
    """Create an attempt_feedback entry."""
    entry_id = await conn.fetchval(
        """
        INSERT INTO attempt_feedback_entry (id, grade_id, call_id, total, feedback, active, mcp, generated)
        VALUES (COALESCE($7, uuidv7()), $1, $2, $3, $4, $5, $6, true)
        RETURNING id
        """,
        grade_id,
        call_id,
        total,
        feedback,
        not soft,
        mcp,
        id,
    )

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

    return CreateAttemptFeedbackResponse(id=entry_id)
