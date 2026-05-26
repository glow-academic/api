"""Entry get — reusable data-access layer."""

from uuid import UUID

import asyncpg  # type: ignore
from redis.asyncio import Redis

from app.tools.entries.attempt_responses.types import (
    GetAttemptResponsesResponse,
)
from app.utils.cache.hedged_row import read_back_row

MV_NAME = "attempt_responses_mv"


async def get_attempt_responses(
    conn: asyncpg.Connection,
    ids: list[UUID],
    redis: Redis,
    *,
    bypass_cache: bool = False,
) -> list[GetAttemptResponsesResponse]:
    """Fetch attempt responses by response IDs."""
    if not ids:
        return []

    cached_results: dict[str, GetAttemptResponsesResponse] = {}
    missing_ids: list[UUID] = []
    if not bypass_cache:
        for rid in ids:
            cached = await read_back_row(redis, "attempt_responses", rid)
            if cached is not None:
                cached_results[str(rid)] = GetAttemptResponsesResponse.model_validate(cached)
            else:
                missing_ids.append(rid)
    else:
        missing_ids = list(ids)

    mv_results: dict[str, GetAttemptResponsesResponse] = {}
    if missing_ids:
        rows = await conn.fetch(
            f"SELECT * FROM {MV_NAME} WHERE response_id = ANY($1)", missing_ids
        )
        for r in rows:
            mv_results[str(r["response_id"])] = GetAttemptResponsesResponse(**dict(r))

    out: list[GetAttemptResponsesResponse] = []
    for rid in ids:
        key = str(rid)
        if key in cached_results:
            out.append(cached_results[key])
        elif key in mv_results:
            out.append(mv_results[key])
    return out
