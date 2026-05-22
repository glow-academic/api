"""Attempt conversations search — filtered/paginated query against attempt_conversations_mv."""

from uuid import UUID

import asyncpg  # type: ignore
from redis.asyncio import Redis

from app.infra.docs.resolve_mv_source import resolve_mv_source
from app.tools.entries.attempt_conversations.types import (
    GetAttemptConversationsResponse,
)
from app.utils.cache.hedged_row import hedged_search

MV_NAME = "attempt_conversations_mv"


async def search_attempt_conversations(
    conn: asyncpg.Connection,
    redis: Redis,
    chat_ids: list[UUID] | None = None,
    mcp: bool | None = None,
    limit: int = 20,
    offset: int = 0,
    bypass_mv: bool = False,
    bypass_cache: bool = False,
) -> list[GetAttemptConversationsResponse]:
    """Search attempt_conversations entries from attempt_conversations_mv with declarative filters."""
    source = await resolve_mv_source(conn, MV_NAME, bypass_mv)

    rows = await conn.fetch(
        f"""
        SELECT id, created_at, generated, mcp, active, chat_id, session_id
        FROM {source}
        WHERE ($1::uuid[] IS NULL OR chat_id = ANY($1))
          AND ($2::boolean IS NULL OR mcp = $2)
        ORDER BY created_at DESC
        LIMIT $3 OFFSET $4
        """,
        chat_ids,
        mcp,
        limit + offset + 1000,
        0,
    )

    mv_dicts = [
        {
            "id": str(r["id"]),
            "created_at": r["created_at"],
            "generated": r["generated"],
            "mcp": r["mcp"],
            "active": r["active"],
            "chat_id": str(r["chat_id"]) if r["chat_id"] else None,
            "session_id": str(r["session_id"]) if r["session_id"] else None,
        }
        for r in rows
    ]

    chat_ids_str = {str(c) for c in chat_ids} if chat_ids else None

    def matches(row: dict) -> bool:
        if chat_ids_str is not None and str(row.get("chat_id")) not in chat_ids_str:
            return False
        if mcp is not None and row.get("mcp") != mcp:
            return False
        return True

    merged = await hedged_search(
        redis,
        "attempt_conversations",
        mv_rows=mv_dicts,
        matches_filter=matches,
        limit=limit,
        offset=offset,
        bypass_cache=bypass_cache,
    )
    return [GetAttemptConversationsResponse.model_validate(r) for r in merged]
