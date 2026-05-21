"""Entry CREATE — reusable data-access layer."""

from datetime import datetime
from uuid import UUID

import asyncpg
from redis.asyncio import Redis

from app.tools.entries.attempt_feedback.types import (
    CreateAttemptFeedbackResponse,
)


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
    entry_id = await conn.fetchval(
        """
        INSERT INTO attempt_feedback_entry (id, grade_id, session_id, total, feedback, active, mcp, generated, created_at)
        VALUES (COALESCE($7, uuidv7()), $1, $2, $3, $4, $5, $6, true, COALESCE($8, NOW()))
        RETURNING id
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
