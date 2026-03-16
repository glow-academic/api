"""Entry get — reusable data-access layer."""

from uuid import UUID

import asyncpg

from app.tools.entries.attempt_home.types import (
    GetAttemptHomeResponse,
)

MV_NAME = "attempt_home_mv"


async def get_attempt_home(
    conn: asyncpg.Connection,
    attempt_ids: list[UUID],
) -> list[GetAttemptHomeResponse]:
    """Get attempt_home entries by attempt_id from MV."""
    if not attempt_ids:
        return []
    rows = await conn.fetch(
        f"SELECT * FROM {MV_NAME} WHERE attempt_id = ANY($1)", attempt_ids
    )
    return [GetAttemptHomeResponse(**dict(r)) for r in rows]
