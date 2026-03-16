"""Entry get — reusable data-access layer."""

from uuid import UUID

import asyncpg

from app.tools.entries.attempt_chat_completion.types import (
    GetAttemptChatCompletionResponse,
)

MV_NAME = "attempt_chat_completion_mv"


async def get_attempt_chat_completions(
    conn: asyncpg.Connection,
    ids: list[UUID],
) -> list[GetAttemptChatCompletionResponse]:
    """Get attempt_chat_completion entries by IDs from MV."""
    if not ids:
        return []
    rows = await conn.fetch(f"SELECT * FROM {MV_NAME} WHERE id = ANY($1)", ids)
    return [GetAttemptChatCompletionResponse(**dict(r)) for r in rows]
