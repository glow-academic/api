"""Attempt message search — filtered/paginated query against attempt_message_mv."""

from uuid import UUID

import asyncpg  # type: ignore
from redis.asyncio import Redis

from app.infra.docs.resolve_mv_source import resolve_mv_source
from app.tools.entries.attempt_message.types import GetAttemptMessageResponse
from app.utils.cache.hedged_row import hedged_search_with_total

MV_NAME = "attempt_message_mv"


async def search_attempt_messages(
    conn: asyncpg.Connection,
    redis: Redis,
    chat_ids: list[UUID] | None = None,
    attempt_ids: list[UUID] | None = None,
    text_ids: list[UUID] | None = None,
    audios_ids: list[UUID] | None = None,
    limit: int = 20,
    offset: int = 0,
    bypass_mv: bool = False,
    bypass_cache: bool = False,
) -> tuple[list[GetAttemptMessageResponse], int]:
    """Search attempt_message entries from attempt_message_mv with declarative filters.

    Returns (items, total_count).
    """
    source = await resolve_mv_source(conn, MV_NAME, bypass_mv)

    rows = await conn.fetch(
        f"""
        SELECT message_id, chat_id, attempt_id, type,
               created_at, completed, text_id,
               history_file_path, audios_id,
               parent_message_id, sibling_index, sibling_count,
               COUNT(*) OVER() AS total_count
        FROM {source}
        WHERE ($1::uuid[] IS NULL OR chat_id = ANY($1))
          AND ($2::uuid[] IS NULL OR attempt_id = ANY($2))
          AND ($3::uuid[] IS NULL OR text_id = ANY($3))
          AND ($4::uuid[] IS NULL OR audios_id = ANY($4))
        ORDER BY created_at DESC
        LIMIT $5 OFFSET $6
        """,
        chat_ids,
        attempt_ids,
        text_ids,
        audios_ids,
        limit + offset + 1000,
        0,
    )

    total_count = rows[0]["total_count"] if rows else 0
    mv_dicts: list[dict] = []
    for r in rows:
        d = {k: v for k, v in dict(r).items() if k != "total_count"}
        d["id"] = str(r["message_id"])
        mv_dicts.append(d)

    chat_ids_str = {str(c) for c in chat_ids} if chat_ids else None
    attempt_ids_str = {str(a) for a in attempt_ids} if attempt_ids else None
    text_ids_str = {str(t) for t in text_ids} if text_ids else None
    audios_ids_str = {str(a) for a in audios_ids} if audios_ids else None

    def matches(row: dict) -> bool:
        if chat_ids_str is not None:
            v = row.get("chat_id")
            if v is None or str(v) not in chat_ids_str:
                return False
        if attempt_ids_str is not None:
            # Cache row may not know attempt_id (derived via chat→attempt join).
            v = row.get("attempt_id")
            if v is None or str(v) not in attempt_ids_str:
                return False
        if text_ids_str is not None:
            # Cache row has text_id=None at create-time; child text_uploads
            # primitive needs to invalidate parent to surface a hit here.
            v = row.get("text_id")
            if v is None or str(v) not in text_ids_str:
                return False
        if audios_ids_str is not None:
            v = row.get("audios_id")
            if v is None or str(v) not in audios_ids_str:
                return False
        return True

    merged, total = await hedged_search_with_total(
        redis,
        "attempt_message",
        mv_rows=mv_dicts,
        mv_total=total_count,
        matches_filter=matches,
        limit=limit,
        offset=offset,
        bypass_cache=bypass_cache,
    )
    items = [
        GetAttemptMessageResponse.model_validate(
            {k: v for k, v in r.items() if k != "id"}
        )
        for r in merged
    ]
    return (items, total)
