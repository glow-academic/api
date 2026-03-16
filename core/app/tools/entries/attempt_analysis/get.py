"""Entry get — reusable data-access layer."""

from uuid import UUID

import asyncpg

from app.tools.entries.attempt_analysis.types import (
    GetAttemptAnalysisResponse,
)

MV_NAME = "attempt_analysis_mv"


async def get_attempt_analyses(
    conn: asyncpg.Connection, ids: list[UUID]
) -> list[GetAttemptAnalysisResponse]:
    if not ids:
        return []
    rows = await conn.fetch(f"SELECT * FROM {MV_NAME} WHERE analysis_id = ANY($1)", ids)
    return [GetAttemptAnalysisResponse(**dict(r)) for r in rows]
