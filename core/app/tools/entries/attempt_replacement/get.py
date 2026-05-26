"""Entry get — reusable data-access layer."""

from uuid import UUID

import asyncpg
from redis.asyncio import Redis

from app.tools.entries.attempt_replacement.types import (
    GetAttemptReplacementResponse,
)
from app.utils.cache.hedged_row import read_back_row

MV_NAME = "attempt_replacement_mv"


async def get_attempt_replacements(
    conn: asyncpg.Connection,
    ids: list[UUID],
    redis: Redis,
    *,
    bypass_cache: bool = False,
) -> list[GetAttemptReplacementResponse]:
    if not ids:
        return []

    cached_results: dict[str, GetAttemptReplacementResponse] = {}
    missing_ids: list[UUID] = []
    if not bypass_cache:
        for rid in ids:
            cached = await read_back_row(redis, "attempt_replacement", rid)
            if cached is not None:
                cached_results[str(rid)] = GetAttemptReplacementResponse.model_validate(cached)
            else:
                missing_ids.append(rid)
    else:
        missing_ids = list(ids)

    mv_results: dict[str, GetAttemptReplacementResponse] = {}
    if missing_ids:
        rows = await conn.fetch(
            f"SELECT * FROM {MV_NAME} WHERE replacement_id = ANY($1)", missing_ids
        )
        for r in rows:
            mv_results[str(r["replacement_id"])] = GetAttemptReplacementResponse(**dict(r))

    out: list[GetAttemptReplacementResponse] = []
    for rid in ids:
        key = str(rid)
        if key in cached_results:
            out.append(cached_results[key])
        elif key in mv_results:
            out.append(mv_results[key])
    return out
