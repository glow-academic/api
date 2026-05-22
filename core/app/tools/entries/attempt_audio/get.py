"""Entry get — reusable data-access layer for attempt_audio.

attempt_audio has no materialized view; fall back to ``attempt_audio_entry``
when the cache misses. Filter for ``active = true`` consistent with the
soft-delete convention used by sibling primitives.
"""

from uuid import UUID

import asyncpg
from redis.asyncio import Redis

from app.tools.entries.attempt_audio.types import GetAttemptAudioResponse
from app.utils.cache.hedged_row import read_back_row


async def get_attempt_audios(
    conn: asyncpg.Connection,
    ids: list[UUID],
    redis: Redis,
    bypass_mv: bool = False,  # accepted for API symmetry; no MV exists
    *,
    bypass_cache: bool = False,
) -> list[GetAttemptAudioResponse]:
    """Get attempt_audio entries by IDs (cache-hedged read from _entry)."""
    if not ids:
        return []

    cached_results: dict[str, GetAttemptAudioResponse] = {}
    missing_ids: list[UUID] = []
    if not bypass_cache:
        for entry_id in ids:
            cached = await read_back_row(redis, "attempt_audio", entry_id)
            if cached is not None:
                cached_results[str(entry_id)] = (
                    GetAttemptAudioResponse.model_validate(cached)
                )
            else:
                missing_ids.append(entry_id)
    else:
        missing_ids = list(ids)

    mv_results: dict[str, GetAttemptAudioResponse] = {}
    if missing_ids:
        rows = await conn.fetch(
            """
            SELECT id, message_id, audios_id, session_id,
                   active, mcp, generated, created_at
            FROM attempt_audio_entry
            WHERE id = ANY($1) AND active = true
            """,
            missing_ids,
        )
        for r in rows:
            mv_results[str(r["id"])] = GetAttemptAudioResponse(**dict(r))

    out: list[GetAttemptAudioResponse] = []
    for entry_id in ids:
        key = str(entry_id)
        if key in cached_results:
            out.append(cached_results[key])
        elif key in mv_results:
            out.append(mv_results[key])
    return out
