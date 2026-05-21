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
    entry_id = await conn.fetchval(
        """
        INSERT INTO test_invocation_runs_entry
            (id, test_invocation_id, run_id, test_invocation_traces_id,
             active, mcp, generated)
        VALUES (COALESCE($6, uuidv7()), $1, $2, $3, $4, $5, true)
        RETURNING id
        """,
        test_invocation_id,
        run_id,
        test_invocation_traces_id,
        not soft,
        mcp,
        id,
    )
    return CreateTestInvocationRunsResponse(id=entry_id)
