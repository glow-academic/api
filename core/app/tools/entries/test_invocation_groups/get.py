"""Entry get — reusable data-access layer."""

from uuid import UUID

import asyncpg

from app.tools.entries.test_invocation_groups.types import (
    GetTestInvocationGroupsResponse,
)

MV_NAME = "test_invocation_groups_mv"


async def get_test_invocation_groups(
    conn: asyncpg.Connection,
    ids: list[UUID],
) -> list[GetTestInvocationGroupsResponse]:
    """Get test_invocation_groups entries by IDs from MV."""
    if not ids:
        return []
    rows = await conn.fetch(
        f"""
        SELECT id, test_invocation_id, created_at, updated_at, generated, mcp, active,
               agent_ids, reasoning_level_ids, temperature_level_ids, voice_ids,
               prompt_ids, instruction_ids, tool_ids, quality_ids, modality_ids
        FROM {MV_NAME}
        WHERE id = ANY($1)
        """,
        ids,
    )
    return [GetTestInvocationGroupsResponse(**dict(r)) for r in rows]
