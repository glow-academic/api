"""Texts search — filtered/paginated query against texts_mv."""

from uuid import UUID

import asyncpg  # type: ignore

from app.infra.docs.resolve_mv_source import resolve_mv_source
from app.tools.entries.texts.types import SearchTextResponse

MV_NAME = "texts_mv"


async def search_texts(
    conn: asyncpg.Connection,
    text_ids: list[UUID] | None = None,
    limit: int = 20,
    offset: int = 0,
    bypass_mv: bool = False,
) -> list[SearchTextResponse]:
    """Search texts from texts_mv with declarative filters."""
    source = await resolve_mv_source(conn, MV_NAME, bypass_mv)

    rows = await conn.fetch(
        f"""
        SELECT texts_id, text_id, upload_id, file_path, mime_type, created_at
        FROM {source}
        WHERE ($1::uuid[] IS NULL OR text_id = ANY($1))
        ORDER BY created_at DESC
        LIMIT $2 OFFSET $3
        """,
        text_ids,
        limit,
        offset,
    )

    return [SearchTextResponse(**dict(r)) for r in rows]
