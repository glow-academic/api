"""Entry CREATE — reusable data-access layer."""

from uuid import UUID

import asyncpg

from app.tools.entries.test_feedback.types import (
    CreateTestFeedbackResponse,
)


async def create_test_feedback(
    conn: asyncpg.Connection,
    grade_id: UUID,
    call_id: UUID,
    total: int,
    *,
    id: UUID | None = None,
    feedback: str = "No feedback provided",
    total_points: int = 0,
    pass_points: int = 0,
    mcp: bool = False,
    soft: bool = False,
) -> CreateTestFeedbackResponse:
    """Create a test_feedback entry."""
    entry_id = await conn.fetchval(
        """
        INSERT INTO test_feedback_entry (id, grade_id, call_id, total, feedback, total_points, pass_points, active, mcp, generated)
        VALUES (COALESCE($9, uuidv7()), $1, $2, $3, $4, $5, $6, $7, $8, true)
        RETURNING id
        """,
        grade_id,
        call_id,
        total,
        feedback,
        total_points,
        pass_points,
        not soft,
        mcp,
        id,
    )
    return CreateTestFeedbackResponse(id=entry_id)
