"""Attempt message search — filtered/paginated query against attempt_message_mv."""

from uuid import UUID

import asyncpg  # type: ignore

from app.infra.docs.resolve_mv_source import resolve_mv_source
from app.tools.entries.attempt_message.types import GetAttemptMessageResponse

MV_NAME = "attempt_message_mv"


async def search_attempt_messages(
    conn: asyncpg.Connection,
    chat_ids: list[UUID] | None = None,
    attempt_ids: list[UUID] | None = None,
    text_ids: list[UUID] | None = None,
    audio_ids: list[UUID] | None = None,
    limit: int = 20,
    offset: int = 0,
    bypass_mv: bool = False,
) -> tuple[list[GetAttemptMessageResponse], int]:
    """Search attempt_message entries from attempt_message_mv with declarative filters.

    Returns (items, total_count).
    """
    source = await resolve_mv_source(conn, MV_NAME, bypass_mv)

    rows = await conn.fetch(
        f"""
        SELECT message_id, chat_id, attempt_id, type,
               created_at, completed, text_id,
               history_file_path, audio_id,
               parent_message_id, sibling_index, sibling_count,
               COUNT(*) OVER() AS total_count
        FROM {source}
        WHERE ($1::uuid[] IS NULL OR chat_id = ANY($1))
          AND ($2::uuid[] IS NULL OR attempt_id = ANY($2))
          AND ($3::uuid[] IS NULL OR text_id = ANY($3))
          AND ($4::uuid[] IS NULL OR audio_id = ANY($4))
        ORDER BY created_at DESC
        LIMIT $5 OFFSET $6
        """,
        chat_ids,
        attempt_ids,
        text_ids,
        audio_ids,
        limit,
        offset,
    )

    total_count = rows[0]["total_count"] if rows else 0
    items = [
        GetAttemptMessageResponse(
            **{k: v for k, v in dict(r).items() if k != "total_count"}
        )
        for r in rows
    ]
    return (items, total_count)
