"""Entry get — reusable data-access layer."""

from uuid import UUID

import asyncpg

from app.tools.entries.attempt_improvement.types import (
    GetAttemptImprovementResponse,
)

MV_NAME = "attempt_improvement_mv"


async def get_attempt_improvements(
    conn: asyncpg.Connection, ids: list[UUID]
) -> list[GetAttemptImprovementResponse]:
    if not ids:
        return []
    rows = await conn.fetch(
        f"SELECT * FROM {MV_NAME} WHERE improvement_id = ANY($1)", ids
    )
    return [GetAttemptImprovementResponse(**dict(r)) for r in rows]
