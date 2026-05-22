"""Entry CREATE — reusable data-access layer."""

from uuid import UUID

import asyncpg
from redis.asyncio import Redis

from app.tools.entries.test_invocation_runs_completion.types import (
    CreateTestInvocationRunsCompletionResponse,
)
from app.utils.cache.hedged_row import write_back_row


async def create_test_invocation_runs_completion(
    conn: asyncpg.Connection,
    redis: Redis,
    test_invocation_runs_id: UUID,
    call_id: UUID,
    *,
    id: UUID | None = None,
    stop: bool = False,
    error: bool = False,
    message: str = "",
    mcp: bool = False,
    soft: bool = False,
) -> CreateTestInvocationRunsCompletionResponse:
    """Create a test_invocation_runs_completion entry."""
    row = await conn.fetchrow(
        """
        INSERT INTO test_invocation_runs_completion_entry (id, test_invocation_runs_id, call_id, stop, error, message, active, mcp, generated)
        VALUES (COALESCE($8, uuidv7()), $1, $2, $3, $4, $5, $6, $7, true)
        RETURNING id, created_at
        """,
        test_invocation_runs_id,
        call_id,
        stop,
        error,
        message,
        not soft,
        mcp,
        id,
    )

    if row is None:
        raise ValueError("Failed to create test_invocation_runs_completion entry")

    entry_id = row["id"]
    created_at = row["created_at"]

    fresh_row = {
        "id": str(entry_id),
        "test_invocation_runs_id": str(test_invocation_runs_id),
        "stop": stop,
        "error": error,
        "message": message,
        "call_id": str(call_id),
        "created_at": created_at.isoformat(),
        "generated": True,
        "mcp": mcp,
        "active": not soft,
    }
    await write_back_row(
        redis,
        "test_invocation_runs_completion",
        entry_id,
        fresh_row,
        score_ms=int(created_at.timestamp() * 1000),
    )

    return CreateTestInvocationRunsCompletionResponse(id=entry_id)
