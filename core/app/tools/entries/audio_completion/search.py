"""Audio completion search — filtered/paginated query against audio_completion_mv."""

from uuid import UUID

import asyncpg  # type: ignore
from redis.asyncio import Redis

from app.infra.docs.resolve_mv_source import resolve_mv_source
from app.tools.entries.audio_completion.types import (
    GetAudioCompletionResponse,
)
from app.utils.cache.hedged_row import hedged_search

MV_NAME = "audio_completion_mv"


async def search_audio_completions(
    conn: asyncpg.Connection,
    redis: Redis,
    audio_ids: list[UUID] | None = None,
    limit: int = 20,
    offset: int = 0,
    bypass_mv: bool = False,
    bypass_cache: bool = False,
) -> list[GetAudioCompletionResponse]:
    """Search audio_completion entries from audio_completion_mv with declarative filters."""
    source = await resolve_mv_source(conn, MV_NAME, bypass_mv)

    rows = await conn.fetch(
        f"""
        SELECT id, audio_id, stop, error, message, session_id, created_at, active, generated, mcp
        FROM {source}
        WHERE ($1::uuid[] IS NULL OR audio_id = ANY($1))
        ORDER BY created_at DESC
        LIMIT $2 OFFSET $3
        """,
        audio_ids,
        limit + offset + 1000,
        0,
    )

    mv_dicts = [
        {
            "id": str(r["id"]),
            "audio_id": str(r["audio_id"]) if r["audio_id"] else None,
            "stop": r["stop"],
            "error": r["error"],
            "message": r["message"],
            "session_id": str(r["session_id"]) if r["session_id"] else None,
            "created_at": r["created_at"],
            "active": r["active"],
            "generated": r["generated"],
            "mcp": r["mcp"],
        }
        for r in rows
    ]

    audio_ids_str = {str(a) for a in audio_ids} if audio_ids else None

    def matches(row: dict) -> bool:
        if audio_ids_str is not None and str(row.get("audio_id")) not in audio_ids_str:
            return False
        return True

    merged = await hedged_search(
        redis,
        "audio_completion",
        mv_rows=mv_dicts,
        matches_filter=matches,
        limit=limit,
        offset=offset,
        bypass_cache=bypass_cache,
    )
    return [GetAudioCompletionResponse.model_validate(r) for r in merged]
