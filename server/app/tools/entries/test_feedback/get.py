"""Entry get — reusable data-access layer."""

from uuid import UUID

import asyncpg

from app.tools.entries.test_feedback.types import (
    GetTestFeedbackResponse,
)

MV_NAME = "test_feedback_mv"


async def get_test_feedbacks(
    conn: asyncpg.Connection, ids: list[UUID]
) -> list[GetTestFeedbackResponse]:
    if not ids:
        return []
    rows = await conn.fetch(f"SELECT * FROM {MV_NAME} WHERE feedback_id = ANY($1)", ids)
    return [GetTestFeedbackResponse(**dict(r)) for r in rows]
