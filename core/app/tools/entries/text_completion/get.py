"""Entry get — reusable data-access layer."""

from uuid import UUID

import asyncpg
from redis.asyncio import Redis

from app.infra.docs.resolve_mv_source import resolve_mv_source
from app.tools.entries.text_completion.types import (
    GetTextCompletionResponse,
)
from app.utils.cache.hedged_row import read_back_row

MV_NAME = "text_completion_mv"


async def get_text_completions(
    conn: asyncpg.Connection,
    ids: list[UUID],
    redis: Redis,
    bypass_mv: bool = False,
    *,
    bypass_cache: bool = False,
) -> list[GetTextCompletionResponse]:
    """Get text_completion entries by IDs from MV (with cache hedge)."""
    if not ids:
        return []

    cached_results: dict[str, GetTextCompletionResponse] = {}
    missing_ids: list[UUID] = []
    if not bypass_cache:
        for entry_id in ids:
            cached = await read_back_row(redis, "text_completion", entry_id)
            if cached is not None:
                cached_results[str(entry_id)] = (
                    GetTextCompletionResponse.model_validate(cached)
                )
            else:
                missing_ids.append(entry_id)
    else:
        missing_ids = list(ids)

    mv_results: dict[str, GetTextCompletionResponse] = {}
    if missing_ids:
        source = await resolve_mv_source(conn, MV_NAME, bypass_mv)
        rows = await conn.fetch(
            f"SELECT * FROM {source} WHERE id = ANY($1)", missing_ids,
        )
        for r in rows:
            mv_results[str(r["id"])] = GetTextCompletionResponse(**dict(r))

    out: list[GetTextCompletionResponse] = []
    for entry_id in ids:
        key = str(entry_id)
        if key in cached_results:
            out.append(cached_results[key])
        elif key in mv_results:
            out.append(mv_results[key])
    return out
