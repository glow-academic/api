"""Entry get — reusable data-access layer."""

from uuid import UUID

import asyncpg  # type: ignore

from app.tools.entries.test_grade.types import GetTestGradeResponse

MV_NAME = "test_grade_mv"


async def get_test_grades(
    conn: asyncpg.Connection, ids: list[UUID]
) -> list[GetTestGradeResponse]:
    """Fetch test grades by IDs."""
    if not ids:
        return []
    rows = await conn.fetch(f"SELECT * FROM {MV_NAME} WHERE id = ANY($1)", ids)
    return [GetTestGradeResponse(**dict(r)) for r in rows]
