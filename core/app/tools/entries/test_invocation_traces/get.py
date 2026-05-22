"""Entry get — reusable data-access layer."""

from uuid import UUID

import asyncpg
from redis.asyncio import Redis

from app.tools.entries.test_invocation_traces.types import (
    GetTestInvocationTracesResponse,
)
from app.utils.cache.hedged_row import read_back_row

MV_NAME = "test_invocation_traces_mv"


async def get_test_invocation_traces(
    conn: asyncpg.Connection,
    ids: list[UUID],
    redis: Redis,
    *,
    bypass_cache: bool = False,
) -> list[GetTestInvocationTracesResponse]:
    """Get test_invocation_traces entries by IDs from MV (with cache hedge)."""
    if not ids:
        return []

    cached_results: dict[str, GetTestInvocationTracesResponse] = {}
    missing_ids: list[UUID] = []
    if not bypass_cache:
        for rid in ids:
            cached = await read_back_row(redis, "test_invocation_traces", rid)
            if cached is not None:
                cached_results[str(rid)] = (
                    GetTestInvocationTracesResponse.model_validate(cached)
                )
            else:
                missing_ids.append(rid)
    else:
        missing_ids = list(ids)

    mv_results: dict[str, GetTestInvocationTracesResponse] = {}
    if missing_ids:
        rows = await conn.fetch(
            f"""
            SELECT id, test_invocation_id, run_id, created_at, updated_at,
                   generated, mcp, active,
                   reasoning_level_ids, temperature_level_ids, voice_ids,
                   prompt_ids, instruction_ids, tool_ids, quality_ids, modality_ids
            FROM {MV_NAME}
            WHERE id = ANY($1)
            """,
            missing_ids,
        )
        for r in rows:
            mv_results[str(r["id"])] = GetTestInvocationTracesResponse(**dict(r))

    out: list[GetTestInvocationTracesResponse] = []
    for rid in ids:
        key = str(rid)
        if key in cached_results:
            out.append(cached_results[key])
        elif key in mv_results:
            out.append(mv_results[key])
    return out
