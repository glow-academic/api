"""Entry get — reusable data-access layer."""

from uuid import UUID

import asyncpg

from app.tools.entries.attempt_practice.types import (
    GetAttemptPracticeResponse,
)

MV_NAME = "attempt_practice_mv"


async def get_attempt_practice(
    conn: asyncpg.Connection,
    attempt_ids: list[UUID],
) -> list[GetAttemptPracticeResponse]:
    """Get attempt_practice entries by attempt_id from MV."""
    if not attempt_ids:
        return []
    rows = await conn.fetch(
        f"SELECT * FROM {MV_NAME} WHERE attempt_id = ANY($1)", attempt_ids
    )
    return [GetAttemptPracticeResponse(**dict(r)) for r in rows]
