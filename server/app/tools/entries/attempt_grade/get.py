"""Entry get — reusable data-access layer."""

from uuid import UUID

import asyncpg  # type: ignore

from app.tools.entries.attempt_grade.types import GetAttemptGradeResponse

MV_NAME = "attempt_grade_mv"


async def get_attempt_grades(
    conn: asyncpg.Connection, ids: list[UUID]
) -> list[GetAttemptGradeResponse]:
    """Fetch attempt grades by grade IDs."""
    if not ids:
        return []
    rows = await conn.fetch(f"SELECT * FROM {MV_NAME} WHERE grade_id = ANY($1)", ids)
    return [GetAttemptGradeResponse(**dict(r)) for r in rows]
