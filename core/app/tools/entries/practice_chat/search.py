"""Practice chat search — filtered/paginated query against practice_chat_mv."""

from uuid import UUID

import asyncpg  # type: ignore

from app.infra.docs.resolve_mv_source import resolve_mv_source
from app.tools.entries.practice_chat.types import GetPracticeChatResponse

MV_NAME = "practice_chat_mv"


async def search_practice_chats(
    conn: asyncpg.Connection,
    practice_ids: list[UUID] | None = None,
    chat_ids: list[UUID] | None = None,
    limit: int = 20,
    offset: int = 0,
    bypass_mv: bool = False,
) -> list[GetPracticeChatResponse]:
    """Search practice_chat entries from practice_chat_mv with declarative filters."""
    source = await resolve_mv_source(conn, MV_NAME, bypass_mv)

    rows = await conn.fetch(
        f"""
        SELECT id, practice_id, chat_id, created_at, active, generated, mcp, session_id
        FROM {source}
        WHERE ($1::uuid[] IS NULL OR practice_id = ANY($1))
          AND ($2::uuid[] IS NULL OR chat_id = ANY($2))
        ORDER BY created_at DESC
        LIMIT $3 OFFSET $4
        """,
        practice_ids,
        chat_ids,
        limit,
        offset,
    )

    return [GetPracticeChatResponse(**dict(r)) for r in rows]
