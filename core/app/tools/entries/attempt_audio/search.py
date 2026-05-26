"""Attempt audio search — filtered/paginated query against attempt_audio_entry.

No materialized view exists for ``attempt_audio``; read directly from the
entry table filtered to active rows, then merge with the hedged cache.
"""

from uuid import UUID

import asyncpg
from redis.asyncio import Redis

from app.tools.entries.attempt_audio.types import GetAttemptAudioResponse
from app.utils.cache.hedged_row import hedged_search


async def search_attempt_audios(
    conn: asyncpg.Connection,
    redis: Redis,
    message_ids: list[UUID] | None = None,
    audios_ids: list[UUID] | None = None,
    session_ids: list[UUID] | None = None,
    limit: int = 20,
    offset: int = 0,
    bypass_cache: bool = False,
) -> list[GetAttemptAudioResponse]:
    """Search attempt_audio entries with declarative filters."""
    rows = await conn.fetch(
        """
        SELECT id, message_id, audios_id, session_id,
               active, mcp, generated, created_at
        FROM attempt_audio_entry
        WHERE active = true
          AND ($1::uuid[] IS NULL OR message_id = ANY($1))
          AND ($2::uuid[] IS NULL OR audios_id = ANY($2))
          AND ($3::uuid[] IS NULL OR session_id = ANY($3))
        ORDER BY created_at DESC
        LIMIT $4 OFFSET $5
        """,
        message_ids,
        audios_ids,
        session_ids,
        limit + offset + 1000,
        0,
    )

    mv_dicts = [
        {
            "id": str(r["id"]),
            "message_id": str(r["message_id"]) if r["message_id"] else None,
            "audios_id": str(r["audios_id"]) if r["audios_id"] else None,
            "session_id": str(r["session_id"]) if r["session_id"] else None,
            "active": r["active"],
            "mcp": r["mcp"],
            "generated": r["generated"],
            "created_at": r["created_at"],
        }
        for r in rows
    ]

    message_ids_str = {str(m) for m in message_ids} if message_ids else None
    audios_ids_str = {str(a) for a in audios_ids} if audios_ids else None
    session_ids_str = {str(s) for s in session_ids} if session_ids else None

    def matches(row: dict) -> bool:
        if row.get("active") is not True:
            return False
        if message_ids_str is not None and str(row.get("message_id")) not in message_ids_str:
            return False
        if audios_ids_str is not None and str(row.get("audios_id")) not in audios_ids_str:
            return False
        if session_ids_str is not None and str(row.get("session_id")) not in session_ids_str:
            return False
        return True

    merged = await hedged_search(
        redis,
        "attempt_audio",
        mv_rows=mv_dicts,
        matches_filter=matches,
        limit=limit,
        offset=offset,
        bypass_cache=bypass_cache,
    )
    return [GetAttemptAudioResponse.model_validate(r) for r in merged]
