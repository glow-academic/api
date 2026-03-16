"""Entry get — reusable data-access layer."""

from uuid import UUID

import asyncpg  # type: ignore

from app.tools.entries.attempt_hint.types import GetAttemptHintResponse

MV_NAME = "attempt_hint_mv"


async def get_attempt_hints(
    conn: asyncpg.Connection, ids: list[UUID]
) -> list[GetAttemptHintResponse]:
    """Fetch attempt hints by hint IDs."""
    if not ids:
        return []
    rows = await conn.fetch(f"SELECT * FROM {MV_NAME} WHERE hint_id = ANY($1)", ids)
    return [GetAttemptHintResponse(**dict(r)) for r in rows]
