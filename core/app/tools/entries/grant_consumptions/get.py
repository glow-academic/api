"""Entry get — reusable data-access layer."""

from uuid import UUID

import asyncpg  # type: ignore
from redis.asyncio import Redis

from app.tools.entries.grant_consumptions.types import (
    GetGrantConsumptionResponse,
)
from app.utils.cache.hedged_row import read_back_row

MV_NAME = "grant_consumptions_mv"


async def get_grant_consumptions(
    conn: asyncpg.Connection,
    ids: list[UUID],
    redis: Redis,
    *,
    bypass_cache: bool = False,
) -> list[GetGrantConsumptionResponse]:
    """Get grant consumption entries by IDs from grant_consumptions_mv."""
    if not ids:
        return []

    cached_results: dict[str, GetGrantConsumptionResponse] = {}
    missing_ids: list[UUID] = []
    if not bypass_cache:
        for cid in ids:
            cached = await read_back_row(redis, "grant_consumptions", cid)
            if cached is not None:
                cached_results[str(cid)] = GetGrantConsumptionResponse.model_validate(cached)
            else:
                missing_ids.append(cid)
    else:
        missing_ids = list(ids)

    mv_results: dict[str, GetGrantConsumptionResponse] = {}
    if missing_ids:
        rows = await conn.fetch(
            f"SELECT * FROM {MV_NAME} WHERE id = ANY($1)", missing_ids,
        )
        for r in rows:
            mv_results[str(r["id"])] = GetGrantConsumptionResponse(**dict(r))

    out: list[GetGrantConsumptionResponse] = []
    for cid in ids:
        key = str(cid)
        if key in cached_results:
            out.append(cached_results[key])
        elif key in mv_results:
            out.append(mv_results[key])
    return out
