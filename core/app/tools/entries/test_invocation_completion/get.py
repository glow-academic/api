"""Entry get — reusable data-access layer."""

from uuid import UUID

import asyncpg

from app.tools.entries.test_invocation_completion.types import (
    GetTestInvocationCompletionResponse,
)

MV_NAME = "test_invocation_completion_mv"


async def get_test_invocation_completions(
    conn: asyncpg.Connection,
    ids: list[UUID],
) -> list[GetTestInvocationCompletionResponse]:
    """Get test_invocation_completion entries by IDs from MV."""
    if not ids:
        return []
    rows = await conn.fetch(f"SELECT * FROM {MV_NAME} WHERE id = ANY($1)", ids)
    return [GetTestInvocationCompletionResponse(**dict(r)) for r in rows]
