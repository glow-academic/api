"""Entry search — filtered/paginated query against test_invocation_groups_mv."""

from uuid import UUID

import asyncpg

from app.tools.entries.test_invocation_groups.types import (
    GetTestInvocationGroupsResponse,
)

MV_NAME = "test_invocation_groups_mv"


async def search_test_invocation_groups(
    conn: asyncpg.Connection,
    test_invocation_ids: list[UUID] | None = None,
    limit: int = 20,
    offset: int = 0,
) -> tuple[list[GetTestInvocationGroupsResponse], int]:
    """Search test_invocation_groups from test_invocation_groups_mv with declarative filters.

    Returns (items, total_count).
    """
    rows = await conn.fetch(
        f"""
        SELECT id, test_invocation_id, created_at, updated_at, generated, mcp, active,
               agent_ids, reasoning_level_ids, temperature_level_ids, voice_ids,
               prompt_ids, instruction_ids, tool_ids, quality_ids, modality_ids,
               COUNT(*) OVER() AS total_count
        FROM {MV_NAME}
        WHERE ($1::uuid[] IS NULL OR test_invocation_id = ANY($1))
        ORDER BY created_at DESC
        LIMIT $2 OFFSET $3
        """,
        test_invocation_ids,
        limit,
        offset,
    )
    total_count = rows[0]["total_count"] if rows else 0
    items = [
        GetTestInvocationGroupsResponse(
            **{k: v for k, v in dict(r).items() if k != "total_count"}
        )
        for r in rows
    ]
    return (items, total_count)
