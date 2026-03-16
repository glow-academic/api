"""Audio Uploads SEARCH — declarative filters."""

from uuid import UUID

import asyncpg

from app.tools.entries.audio_uploads.types import GetAudioUploadResponse


async def search_audio_uploads(
    conn: asyncpg.Connection,
    audio_ids: list[UUID] | None = None,
    upload_ids: list[UUID] | None = None,
    session_ids: list[UUID] | None = None,
    limit: int = 20,
    offset: int = 0,
) -> list[GetAudioUploadResponse]:
    """Search audio_uploads entries with declarative filters."""
    rows = await conn.fetch(
        """
        SELECT id, audio_id, upload_id, session_id, created_at, active, mcp, generated
        FROM audio_uploads_entry
        WHERE active = true
          AND ($1::uuid[] IS NULL OR audio_id = ANY($1))
          AND ($2::uuid[] IS NULL OR upload_id = ANY($2))
          AND ($3::uuid[] IS NULL OR session_id = ANY($3))
        ORDER BY created_at DESC
        LIMIT $4 OFFSET $5
        """,
        audio_ids,
        upload_ids,
        session_ids,
        limit,
        offset,
    )
    return [
        GetAudioUploadResponse(
            id=r["id"],
            audio_id=r["audio_id"],
            upload_id=r["upload_id"],
            session_id=r["session_id"],
            created_at=r["created_at"],
            active=r["active"],
            mcp=r["mcp"],
            generated=r["generated"],
        )
        for r in rows
    ]
