"""Entry CREATE — reusable data-access layer."""

from uuid import UUID

import asyncpg
from redis.asyncio import Redis

from app.tools.entries.test_completion.types import (
    CreateTestCompletionResponse,
)
from app.utils.cache.hedged_row import write_back_row


async def create_test_completion(
    conn: asyncpg.Connection,
    redis: Redis,
    test_id: UUID,
    call_id: UUID,
    *,
    id: UUID | None = None,
    stop: bool = False,
    error: bool = False,
    message: str = "",
    mcp: bool = False,
    soft: bool = False,
) -> CreateTestCompletionResponse:
    """Create a test_completion entry."""
    row = await conn.fetchrow(
        """
        INSERT INTO test_completion_entry (id, test_id, call_id, stop, error, message, active, mcp, generated)
        VALUES (COALESCE($8, uuidv7()), $1, $2, $3, $4, $5, $6, $7, true)
        RETURNING id, created_at
        """,
        test_id,
        call_id,
        stop,
        error,
        message,
        not soft,
        mcp,
        id,
    )

    if row is None:
        raise ValueError("Failed to create test_completion entry")

    entry_id = row["id"]
    created_at = row["created_at"]

    fresh_row = {
        "id": str(entry_id),
        "test_id": str(test_id),
        "stop": stop,
        "error": error,
        "message": message,
        "call_id": str(call_id),
        "created_at": created_at.isoformat(),
        "active": not soft,
        "generated": True,
        "mcp": mcp,
    }
    await write_back_row(
        redis,
        "test_completion",
        entry_id,
        fresh_row,
        score_ms=int(created_at.timestamp() * 1000),
    )

    return CreateTestCompletionResponse(id=entry_id)
