"""Attempt conversations search — filtered/paginated query against attempt_conversations_mv."""

from uuid import UUID

import asyncpg  # type: ignore

from app.infra.docs.resolve_mv_source import resolve_mv_source
from app.tools.entries.attempt_conversations.types import (
    GetAttemptConversationsResponse,
)

MV_NAME = "attempt_conversations_mv"


async def search_attempt_conversations(
    conn: asyncpg.Connection,
    chat_ids: list[UUID] | None = None,
    mcp: bool | None = None,
    limit: int = 20,
    offset: int = 0,
    bypass_mv: bool = False,
) -> list[GetAttemptConversationsResponse]:
    """Search attempt_conversations entries from attempt_conversations_mv with declarative filters."""
    source = await resolve_mv_source(conn, MV_NAME, bypass_mv)

    rows = await conn.fetch(
        f"""
        SELECT id, created_at, generated, mcp, active, chat_id, run_id, call_id
        FROM {source}
        WHERE ($1::uuid[] IS NULL OR chat_id = ANY($1))
          AND ($2::boolean IS NULL OR mcp = $2)
        ORDER BY created_at DESC
        LIMIT $3 OFFSET $4
        """,
        chat_ids,
        mcp,
        limit,
        offset,
    )

    return [GetAttemptConversationsResponse(**dict(r)) for r in rows]
