"""Entry get — reusable data-access layer."""

from uuid import UUID

import asyncpg

from app.tools.entries.attempt_conversation_completion.types import (
    GetAttemptConversationCompletionResponse,
)

MV_NAME = "attempt_conversation_completion_mv"


async def get_attempt_conversation_completions(
    conn: asyncpg.Connection,
    ids: list[UUID],
) -> list[GetAttemptConversationCompletionResponse]:
    """Get attempt_conversation_completion entries by IDs from MV."""
    if not ids:
        return []
    rows = await conn.fetch(f"SELECT * FROM {MV_NAME} WHERE id = ANY($1)", ids)
    return [GetAttemptConversationCompletionResponse(**dict(r)) for r in rows]
