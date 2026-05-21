"""Entry get — reusable data-access layer."""

from uuid import UUID

import asyncpg
from redis.asyncio import Redis

from app.tools.entries.test_invocation_runs.types import (
    GetTestInvocationRunsResponse,
)

MV_NAME = "test_invocation_runs_mv"


async def get_test_invocation_runs(
    conn: asyncpg.Connection,
    ids: list[UUID],
    redis: Redis) -> list[GetTestInvocationRunsResponse]:
    """Get test_invocation_runs entries by IDs from MV."""
    if not ids:
        return []
    rows = await conn.fetch(
        f"""
        SELECT id, test_invocation_id, test_invocation_traces_id, run_id,
               created_at, updated_at, generated, mcp, active
        FROM {MV_NAME}
        WHERE id = ANY($1)
        """,
        ids,
    )
    return [GetTestInvocationRunsResponse(**dict(r)) for r in rows]
