"""Home chat search — filtered/paginated query against home_chat_mv."""

from uuid import UUID

import asyncpg  # type: ignore
from redis.asyncio import Redis

from app.infra.docs.resolve_mv_source import resolve_mv_source
from app.tools.entries.home_chat.types import GetHomeChatResponse
from app.utils.cache.hedged_row import hedged_search

MV_NAME = "home_chat_mv"


async def search_home_chats(
    conn: asyncpg.Connection,
    redis: Redis,
    home_ids: list[UUID] | None = None,
    chat_ids: list[UUID] | None = None,
    limit: int = 20,
    offset: int = 0,
    bypass_mv: bool = False,
    bypass_cache: bool = False,
) -> list[GetHomeChatResponse]:
    """Search home_chat entries from home_chat_mv with declarative filters."""
    source = await resolve_mv_source(conn, MV_NAME, bypass_mv)

    rows = await conn.fetch(
        f"""
        SELECT id, home_id, chat_id, created_at, active, generated, mcp, session_id
        FROM {source}
        WHERE ($1::uuid[] IS NULL OR home_id = ANY($1))
          AND ($2::uuid[] IS NULL OR chat_id = ANY($2))
        ORDER BY created_at DESC
        LIMIT $3 OFFSET $4
        """,
        home_ids,
        chat_ids,
        limit + offset + 1000,
        0,
    )

    mv_dicts = [
        {
            "id": str(r["id"]),
            "home_id": str(r["home_id"]),
            "chat_id": str(r["chat_id"]),
            "created_at": r["created_at"],
            "active": r["active"],
            "generated": r["generated"],
            "mcp": r["mcp"],
            "session_id": str(r["session_id"]),
        }
        for r in rows
    ]

    home_ids_str = {str(h) for h in home_ids} if home_ids else None
    chat_ids_str = {str(c) for c in chat_ids} if chat_ids else None

    def matches(row: dict) -> bool:
        if home_ids_str is not None and str(row.get("home_id")) not in home_ids_str:
            return False
        if chat_ids_str is not None and str(row.get("chat_id")) not in chat_ids_str:
            return False
        return True

    merged = await hedged_search(
        redis,
        "home_chat",
        mv_rows=mv_dicts,
        matches_filter=matches,
        limit=limit,
        offset=offset,
        bypass_cache=bypass_cache,
    )
    return [GetHomeChatResponse.model_validate(r) for r in merged]
