"""Attempt chat completion search — filtered/paginated query against attempt_chat_completion_mv."""

from uuid import UUID

import asyncpg  # type: ignore
from redis.asyncio import Redis

from app.infra.docs.resolve_mv_source import resolve_mv_source
from app.tools.entries.attempt_chat_completion.types import (
    GetAttemptChatCompletionResponse,
)
from app.utils.cache.hedged_row import hedged_search

MV_NAME = "attempt_chat_completion_mv"


async def search_attempt_chat_completions(
    conn: asyncpg.Connection,
    redis: Redis,
    chat_ids: list[UUID] | None = None,
    limit: int = 20,
    offset: int = 0,
    bypass_mv: bool = False,
    bypass_cache: bool = False,
) -> list[GetAttemptChatCompletionResponse]:
    """Search attempt_chat_completion entries from attempt_chat_completion_mv with declarative filters."""
    source = await resolve_mv_source(conn, MV_NAME, bypass_mv)

    rows = await conn.fetch(
        f"""
        SELECT id, chat_id, stop, error, message, created_at, active, generated, mcp, session_id
        FROM {source}
        WHERE ($1::uuid[] IS NULL OR chat_id = ANY($1))
        ORDER BY created_at DESC
        LIMIT $2 OFFSET $3
        """,
        chat_ids,
        limit + offset + 1000,
        0,
    )

    mv_dicts = [
        {
            "id": str(r["id"]),
            "chat_id": str(r["chat_id"]) if r["chat_id"] else None,
            "stop": r["stop"],
            "error": r["error"],
            "message": r["message"],
            "created_at": r["created_at"],
            "active": r["active"],
            "generated": r["generated"],
            "mcp": r["mcp"],
            "session_id": str(r["session_id"]) if r["session_id"] else None,
        }
        for r in rows
    ]

    chat_ids_str = {str(c) for c in chat_ids} if chat_ids else None

    def matches(row: dict) -> bool:
        if chat_ids_str is not None and str(row.get("chat_id")) not in chat_ids_str:
            return False
        return True

    merged = await hedged_search(
        redis,
        "attempt_chat_completion",
        mv_rows=mv_dicts,
        matches_filter=matches,
        limit=limit,
        offset=offset,
        bypass_cache=bypass_cache,
    )
    return [GetAttemptChatCompletionResponse.model_validate(r) for r in merged]
