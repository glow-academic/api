"""Entry get — reusable data-access layer."""

from uuid import UUID

import asyncpg

from app.tools.entries.attempt_conversations.types import (
    GetAttemptConversationsResponse,
)

MV_NAME = "attempt_conversations_mv"


async def get_attempt_conversations(
    conn: asyncpg.Connection,
    ids: list[UUID],
) -> list[GetAttemptConversationsResponse]:
    """Get attempt_conversations entries by IDs from MV."""
    if not ids:
        return []
    rows = await conn.fetch(f"SELECT * FROM {MV_NAME} WHERE id = ANY($1)", ids)
    return [GetAttemptConversationsResponse(**dict(r)) for r in rows]
