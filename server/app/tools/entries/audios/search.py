"""Audios search — filtered/paginated query against audios_mv."""

from uuid import UUID

import asyncpg  # type: ignore

from app.infra.docs.resolve_mv_source import resolve_mv_source
from app.tools.entries.audios.types import SearchAudioResponse

MV_NAME = "audios_mv"


async def search_audios(
    conn: asyncpg.Connection,
    voice_ids: list[UUID] | None = None,
    limit: int = 20,
    offset: int = 0,
    bypass_mv: bool = False,
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
        limit,
        offset,
    )

    return [SearchAudioResponse(**dict(r)) for r in rows]
