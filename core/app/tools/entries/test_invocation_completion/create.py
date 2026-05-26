"""Entry CREATE — reusable data-access layer."""

from uuid import UUID

import asyncpg
from redis.asyncio import Redis

from app.tools.entries.test_invocation_completion.types import (
    CreateTestInvocationCompletionResponse,
)
from app.utils.cache.hedged_row import write_back_row


async def create_test_invocation_completion(
    conn: asyncpg.Connection,
    redis: Redis,
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
    row = await conn.fetchrow(
        """
        INSERT INTO test_invocation_completion_entry (id, invocation_id, call_id, stop, error, message, active, mcp, generated)
        VALUES (COALESCE($8, uuidv7()), $1, $2, $3, $4, $5, $6, $7, true)
        RETURNING id, created_at
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
    entry_id = row["id"]
    created_at = row["created_at"]

    fresh_row = {
        "id": str(entry_id),
        "created_at": created_at.isoformat(),
        "generated": True,
        "mcp": mcp,
        "active": not soft,
        "invocation_id": str(invocation_id),
        "stop": stop,
        "error": error,
        "message": message,
        "call_id": str(call_id),
    }
    await write_back_row(
        redis,
        "test_invocation_completion",
        entry_id,
        fresh_row,
        score_ms=int(created_at.timestamp() * 1000),
    )

    return CreateTestInvocationCompletionResponse(id=entry_id)
