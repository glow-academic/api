"""Entry get — reusable data-access layer."""

from uuid import UUID

import asyncpg  # type: ignore

from app.tools.entries.attempt_content.types import (
    GetAttemptContentResponse,
)

MV_NAME = "attempt_content_mv"


async def get_attempt_contents(
    conn: asyncpg.Connection, ids: list[UUID]
) -> list[GetAttemptContentResponse]:
    """Fetch attempt contents by content IDs."""
    if not ids:
        return []
    rows = await conn.fetch(f"SELECT * FROM {MV_NAME} WHERE content_id = ANY($1)", ids)
    return [GetAttemptContentResponse(**dict(r)) for r in rows]
