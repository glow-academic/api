"""Entry get — reusable data-access layer."""

from uuid import UUID

import asyncpg

from app.tools.entries.attempt_feedback.types import (
    GetAttemptFeedbackResponse,
)

MV_NAME = "attempt_feedback_mv"


async def get_attempt_feedbacks(
    conn: asyncpg.Connection, ids: list[UUID]
) -> list[GetAttemptFeedbackResponse]:
    if not ids:
        return []
    rows = await conn.fetch(f"SELECT * FROM {MV_NAME} WHERE feedback_id = ANY($1)", ids)
    return [GetAttemptFeedbackResponse(**dict(r)) for r in rows]
