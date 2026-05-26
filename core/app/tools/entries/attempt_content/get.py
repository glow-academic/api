"""Entry get — reusable data-access layer."""

from uuid import UUID

import asyncpg  # type: ignore
from redis.asyncio import Redis

from app.tools.entries.attempt_content.types import (
    GetAttemptContentResponse,
)
from app.utils.cache.hedged_row import read_back_row

MV_NAME = "attempt_content_mv"


async def get_attempt_contents(
    conn: asyncpg.Connection,
    ids: list[UUID],
    redis: Redis,
    *,
    bypass_cache: bool = False,
) -> list[GetAttemptContentResponse]:
    """Fetch attempt contents by content IDs (with cache hedge)."""
    if not ids:
        return []

    cached_results: dict[str, GetAttemptContentResponse] = {}
    missing_ids: list[UUID] = []
    if not bypass_cache:
        for entry_id in ids:
            cached = await read_back_row(redis, "attempt_content", entry_id)
            if cached is not None:
                cached_results[str(entry_id)] = (
                    GetAttemptContentResponse.model_validate(cached)
                )
            else:
                missing_ids.append(entry_id)
    else:
        missing_ids = list(ids)

    mv_results: dict[str, GetAttemptContentResponse] = {}
    if missing_ids:
        rows = await conn.fetch(
            f"SELECT * FROM {MV_NAME} WHERE content_id = ANY($1)", missing_ids,
        )
        for r in rows:
            mv_results[str(r["content_id"])] = GetAttemptContentResponse(**dict(r))

    out: list[GetAttemptContentResponse] = []
    for entry_id in ids:
        key = str(entry_id)
        if key in cached_results:
            out.append(cached_results[key])
        elif key in mv_results:
            out.append(mv_results[key])
    return out
