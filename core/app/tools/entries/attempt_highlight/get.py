"""Entry get — reusable data-access layer."""

from uuid import UUID

import asyncpg
from redis.asyncio import Redis

from app.infra.docs.resolve_mv_source import resolve_mv_source
from app.tools.entries.attempt_highlight.types import (
    GetAttemptHighlightResponse,
)
from app.utils.cache.hedged_row import read_back_row

MV_NAME = "attempt_highlight_mv"


async def get_attempt_highlights(
    conn: asyncpg.Connection,
    ids: list[UUID],
    redis: Redis,
    bypass_mv: bool = False,
    *,
    bypass_cache: bool = False,
) -> list[GetAttemptHighlightResponse]:
    if not ids:
        return []

    cached_results: dict[str, GetAttemptHighlightResponse] = {}
    missing_ids: list[UUID] = []
    if not bypass_cache:
        for entry_id in ids:
            cached = await read_back_row(redis, "attempt_highlight", entry_id)
            if cached is not None:
                cached_results[str(entry_id)] = (
                    GetAttemptHighlightResponse.model_validate(cached)
                )
            else:
                missing_ids.append(entry_id)
    else:
        missing_ids = list(ids)

    mv_results: dict[str, GetAttemptHighlightResponse] = {}
    if missing_ids:
        source = await resolve_mv_source(conn, MV_NAME, bypass_mv)
        rows = await conn.fetch(
            f"SELECT * FROM {source} WHERE highlight_id = ANY($1)", missing_ids,
        )
        for r in rows:
            mv_results[str(r["highlight_id"])] = GetAttemptHighlightResponse(
                **dict(r)
            )

    out: list[GetAttemptHighlightResponse] = []
    for entry_id in ids:
        key = str(entry_id)
        if key in cached_results:
            out.append(cached_results[key])
        elif key in mv_results:
            out.append(mv_results[key])
    return out
