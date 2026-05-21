"""Entry get — reusable data-access layer."""

from uuid import UUID

import asyncpg
from redis.asyncio import Redis

from app.tools.entries.test_invocation_traces.types import (
    GetTestInvocationTracesResponse,
)

MV_NAME = "test_invocation_traces_mv"


async def get_test_invocation_traces(
    conn: asyncpg.Connection,
    ids: list[UUID],
    redis: Redis) -> list[GetTestInvocationTracesResponse]:
    """Get test_invocation_traces entries by IDs from MV."""
    if not ids:
        return []
    rows = await conn.fetch(
        f"""
        SELECT id, test_invocation_id, run_id, created_at, updated_at,
               generated, mcp, active,
               reasoning_level_ids, temperature_level_ids, voice_ids,
               prompt_ids, instruction_ids, tool_ids, quality_ids, modality_ids
        FROM {MV_NAME}
        WHERE id = ANY($1)
        """,
        ids,
    )
    return [GetTestInvocationTracesResponse(**dict(r)) for r in rows]
