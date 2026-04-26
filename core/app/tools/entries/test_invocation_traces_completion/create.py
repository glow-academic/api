"""Entry CREATE — reusable data-access layer."""

from uuid import UUID

import asyncpg

from app.tools.entries.test_invocation_traces_completion.types import (
    CreateTestInvocationTracesCompletionResponse,
)


async def create_test_invocation_traces_completion(
    conn: asyncpg.Connection,
    test_invocation_traces_id: UUID,
    call_id: UUID,
    *,
    id: UUID | None = None,
    stop: bool = False,
    error: bool = False,
    message: str = "",
    mcp: bool = False,
    soft: bool = False,
) -> CreateTestInvocationTracesCompletionResponse:
    """Create a test_invocation_traces_completion entry."""
    entry_id = await conn.fetchval(
        """
        INSERT INTO test_invocation_traces_completion_entry
            (id, test_invocation_traces_id, call_id, stop, error, message, active, mcp, generated)
        VALUES (COALESCE($8, uuidv7()), $1, $2, $3, $4, $5, $6, $7, true)
        RETURNING id
        """,
        test_invocation_traces_id,
        call_id,
        stop,
        error,
        message,
        not soft,
        mcp,
        id,
    )
    return CreateTestInvocationTracesCompletionResponse(id=entry_id)
