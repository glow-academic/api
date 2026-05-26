"""Audios search — filtered/paginated query against audios_mv."""

from uuid import UUID

import asyncpg  # type: ignore
from redis.asyncio import Redis

from app.infra.docs.resolve_mv_source import resolve_mv_source
from app.tools.entries.audios.types import SearchAudioResponse
from app.utils.cache.hedged_row import hedged_search

MV_NAME = "audios_mv"


async def search_audios(
    conn: asyncpg.Connection,
    redis: Redis,
    voice_ids: list[UUID] | None = None,
    limit: int = 20,
    offset: int = 0,
    bypass_mv: bool = False,
    bypass_cache: bool = False,
) -> list[SearchAudioResponse]:
    """Search audios from audios_mv with declarative filters."""
    source = await resolve_mv_source(conn, MV_NAME, bypass_mv)

    rows = await conn.fetch(
        f"""
        SELECT audio_id, upload_id, file_path, mime_type, size,
               length_seconds, voice_id, created_at
        FROM {source}
        WHERE ($1::uuid[] IS NULL OR voice_id = ANY($1))
        ORDER BY created_at DESC
        LIMIT $2 OFFSET $3
        """,
        voice_ids,
        limit + offset + 1000,
        0,
    )

    mv_dicts = [
        {
            "audio_id": str(r["audio_id"]),
            "upload_id": str(r["upload_id"]) if r["upload_id"] else None,
            "file_path": r["file_path"],
            "mime_type": r["mime_type"],
            "size": r["size"],
            "length_seconds": r["length_seconds"],
            "voice_id": str(r["voice_id"]) if r["voice_id"] else None,
            "created_at": r["created_at"],
        }
        for r in rows
    ]

    voice_ids_str = {str(v) for v in voice_ids} if voice_ids else None

    def matches(row: dict) -> bool:
        if voice_ids_str is not None and str(row.get("voice_id")) not in voice_ids_str:
            return False
        return True

    merged = await hedged_search(
        redis,
        "audios",
        mv_rows=mv_dicts,
        matches_filter=matches,
        limit=limit,
        offset=offset,
        id_key="audio_id",
        bypass_cache=bypass_cache,
    )
    return [SearchAudioResponse.model_validate(r) for r in merged]
