"""Entry search — filtered/paginated query against test_invocation_runs_completion_mv."""

from uuid import UUID

import asyncpg

from app.tools.entries.test_invocation_runs_completion.types import (
    GetTestInvocationRunsCompletionResponse,
)

MV_NAME = "test_invocation_runs_completion_mv"


async def search_test_invocation_runs_completion(
    conn: asyncpg.Connection,
    test_invocation_runs_ids: list[UUID] | None = None,
    limit: int = 20,
    offset: int = 0,
) -> tuple[list[GetTestInvocationRunsCompletionResponse], int]:
    """Search test_invocation_runs_completion entries with declarative filters.

    Returns (items, total_count).
    """
    rows = await conn.fetch(
        f"""
        SELECT id, test_invocation_runs_id, stop, error, message, call_id,
               created_at, generated, mcp, active,
               COUNT(*) OVER() AS total_count
        FROM {MV_NAME}
        WHERE ($1::uuid[] IS NULL OR test_invocation_runs_id = ANY($1))
        ORDER BY created_at DESC
        LIMIT $2 OFFSET $3
        """,
        test_invocation_runs_ids,
        limit,
        offset,
    )
    total_count = rows[0]["total_count"] if rows else 0
    items = [
        GetTestInvocationRunsCompletionResponse(
            **{k: v for k, v in dict(r).items() if k != "total_count"}
        )
        for r in rows
    ]
    return (items, total_count)
