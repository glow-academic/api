"""Entry get — reusable data-access layer."""

from uuid import UUID

import asyncpg
from redis.asyncio import Redis

from app.tools.entries.test_invocation_completion.types import (
    GetTestInvocationCompletionResponse,
)
from app.utils.cache.hedged_row import read_back_row

MV_NAME = "test_invocation_completion_mv"


async def get_test_invocation_completions(
    conn: asyncpg.Connection,
    ids: list[UUID],
    redis: Redis,
    *,
    bypass_cache: bool = False,
) -> list[GetTestInvocationCompletionResponse]:
    """Get test_invocation_completion entries by IDs from MV (with cache hedge)."""
    if not ids:
        return []

    cached_results: dict[str, GetTestInvocationCompletionResponse] = {}
    missing_ids: list[UUID] = []
    if not bypass_cache:
        for rid in ids:
            cached = await read_back_row(redis, "test_invocation_completion", rid)
            if cached is not None:
                cached_results[str(rid)] = (
                    GetTestInvocationCompletionResponse.model_validate(cached)
                )
            else:
                missing_ids.append(rid)
    else:
        missing_ids = list(ids)

    mv_results: dict[str, GetTestInvocationCompletionResponse] = {}
    if missing_ids:
        rows = await conn.fetch(
            f"SELECT * FROM {MV_NAME} WHERE id = ANY($1)", missing_ids,
        )
        for r in rows:
            mv_results[str(r["id"])] = GetTestInvocationCompletionResponse(**dict(r))

    out: list[GetTestInvocationCompletionResponse] = []
    for rid in ids:
        key = str(rid)
        if key in cached_results:
            out.append(cached_results[key])
        elif key in mv_results:
            out.append(mv_results[key])
    return out
