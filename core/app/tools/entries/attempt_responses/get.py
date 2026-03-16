"""Entry get — reusable data-access layer."""

from uuid import UUID

import asyncpg  # type: ignore

from app.tools.entries.attempt_responses.types import (
    GetAttemptResponsesResponse,
)

MV_NAME = "attempt_responses_mv"


async def get_attempt_responses(
    conn: asyncpg.Connection, ids: list[UUID]
) -> list[GetAttemptResponsesResponse]:
    """Fetch attempt responses by response IDs."""
    if not ids:
        return []
    rows = await conn.fetch(f"SELECT * FROM {MV_NAME} WHERE response_id = ANY($1)", ids)
    return [GetAttemptResponsesResponse(**dict(r)) for r in rows]
