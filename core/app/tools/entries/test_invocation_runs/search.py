"""Entry search — filtered/paginated query against test_invocation_runs_mv."""

from uuid import UUID

import asyncpg
from redis.asyncio import Redis

from app.tools.entries.test_invocation_runs.types import (
    GetTestInvocationRunsResponse,
)

MV_NAME = "test_invocation_runs_mv"


async def search_test_invocation_runs(
    conn: asyncpg.Connection,
    redis: Redis,
    test_invocation_ids: list[UUID] | None = None,
    test_invocation_traces_ids: list[UUID] | None = None,
    limit: int = 20,
    offset: int = 0,
) -> tuple[list[GetTestInvocationRunsResponse], int]:
    """Search test_invocation_runs from test_invocation_runs_mv with declarative filters.

    Returns (items, total_count).
    """
    rows = await conn.fetch(
        f"""
        SELECT id, test_invocation_id, test_invocation_traces_id, run_id,
               created_at, updated_at, generated, mcp, active,
               COUNT(*) OVER() AS total_count
        FROM {MV_NAME}
        WHERE ($1::uuid[] IS NULL OR test_invocation_id = ANY($1))
          AND ($2::uuid[] IS NULL OR test_invocation_traces_id = ANY($2))
        ORDER BY created_at DESC
        LIMIT $3 OFFSET $4
        """,
        test_invocation_ids,
        test_invocation_traces_ids,
        limit,
        offset,
    )
    total_count = rows[0]["total_count"] if rows else 0
    items = [
        GetTestInvocationRunsResponse(
            **{k: v for k, v in dict(r).items() if k != "total_count"}
        )
        for r in rows
    ]
    return (items, total_count)
