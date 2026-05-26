"""Entry get — reusable data-access layer."""

from uuid import UUID

import asyncpg
from redis.asyncio import Redis

from app.tools.entries.attempt_archive.types import (
    GetAttemptArchiveResponse,
)
from app.utils.cache.hedged_row import read_back_row

MV_NAME = "attempt_archive_mv"


async def get_attempt_archives(
    conn: asyncpg.Connection,
    ids: list[UUID],
    redis: Redis,
    *,
    bypass_cache: bool = False,
) -> list[GetAttemptArchiveResponse]:
    """Get attempt_archive entries by IDs from MV (with cache hedge)."""
    if not ids:
        return []

    cached_results: dict[str, GetAttemptArchiveResponse] = {}
    missing_ids: list[UUID] = []
    if not bypass_cache:
        for entry_id in ids:
            cached = await read_back_row(redis, "attempt_archive", entry_id)
            if cached is not None:
                cached_results[str(entry_id)] = GetAttemptArchiveResponse.model_validate(cached)
            else:
                missing_ids.append(entry_id)
    else:
        missing_ids = list(ids)

    mv_results: dict[str, GetAttemptArchiveResponse] = {}
    if missing_ids:
        rows = await conn.fetch(f"SELECT * FROM {MV_NAME} WHERE id = ANY($1)", missing_ids)
        for r in rows:
            item = GetAttemptArchiveResponse(**dict(r))
            mv_results[str(item.id)] = item

    out: list[GetAttemptArchiveResponse] = []
    for entry_id in ids:
        key = str(entry_id)
        if key in cached_results:
            out.append(cached_results[key])
        elif key in mv_results:
            out.append(mv_results[key])
    return out
