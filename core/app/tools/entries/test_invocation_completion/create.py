"""Entry CREATE — reusable data-access layer."""

from uuid import UUID

import asyncpg

from app.tools.entries.test_invocation_completion.types import (
    CreateTestInvocationCompletionResponse,
)


async def create_test_invocation_completion(
    conn: asyncpg.Connection,
    invocation_id: UUID,
    call_id: UUID,
    *,
    id: UUID | None = None,
    stop: bool = False,
    error: bool = False,
    message: str = "",
    mcp: bool = False,
    soft: bool = False,
) -> CreateTestInvocationCompletionResponse:
    """Create a test_invocation_completion entry."""
    entry_id = await conn.fetchval(
        """
        INSERT INTO test_invocation_completion_entry (id, invocation_id, call_id, stop, error, message, active, mcp, generated)
        VALUES (COALESCE($8, uuidv7()), $1, $2, $3, $4, $5, $6, $7, true)
        RETURNING id
        """,
        invocation_id,
        call_id,
        stop,
        error,
        message,
        not soft,
        mcp,
        id,
    )
    return CreateTestInvocationCompletionResponse(id=entry_id)
