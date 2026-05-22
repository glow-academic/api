"""Entry CREATE — reusable data-access layer.

Pure binding row: links a test invocation to (a) the underlying runs_entry
that holds the model output, and (b) the parent test_invocation_traces_entry
that carries the bundle config. No connection tables — bundle config lives
on the trace.
"""

from uuid import UUID

import asyncpg
from redis.asyncio import Redis

from app.tools.entries.test_invocation_runs.types import (
    CreateTestInvocationRunsResponse,
)
from app.utils.cache.hedged_row import write_back_row


async def create_test_invocation_runs(
    conn: asyncpg.Connection,
    redis: Redis,
    test_invocation_id: UUID,
    *,
    id: UUID | None = None,
    run_id: UUID | None = None,
    test_invocation_traces_id: UUID | None = None,
    mcp: bool = False,
    soft: bool = False,
) -> CreateTestInvocationRunsResponse:
    """Create a test_invocation_runs entry binding row."""
    row = await conn.fetchrow(
        """
        INSERT INTO test_invocation_runs_entry
            (id, test_invocation_id, run_id, test_invocation_traces_id,
             active, mcp, generated)
        VALUES (COALESCE($6, uuidv7()), $1, $2, $3, $4, $5, true)
        RETURNING id, created_at, updated_at
        """,
        test_invocation_id,
        run_id,
        test_invocation_traces_id,
        not soft,
        mcp,
        id,
    )

    if row is None:
        raise ValueError("Failed to create test_invocation_runs entry")

    entry_id = row["id"]
    created_at = row["created_at"]
    updated_at = row["updated_at"]

    fresh_row = {
        "id": str(entry_id),
        "test_invocation_id": str(test_invocation_id),
        "test_invocation_traces_id": (
            str(test_invocation_traces_id) if test_invocation_traces_id else None
        ),
        "run_id": str(run_id) if run_id else None,
        "created_at": created_at.isoformat(),
        "updated_at": updated_at.isoformat() if updated_at else created_at.isoformat(),
        "generated": True,
        "mcp": mcp,
        "active": not soft,
    }
    await write_back_row(
        redis,
        "test_invocation_runs",
        entry_id,
        fresh_row,
        score_ms=int(created_at.timestamp() * 1000),
    )

    return CreateTestInvocationRunsResponse(id=entry_id)
