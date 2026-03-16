"""Attempt chat completion search — filtered/paginated query against attempt_chat_completion_mv."""

from uuid import UUID

import asyncpg  # type: ignore

from app.infra.docs.resolve_mv_source import resolve_mv_source
from app.tools.entries.attempt_chat_completion.types import (
    GetAttemptChatCompletionResponse,
)

MV_NAME = "attempt_chat_completion_mv"


async def search_attempt_chat_completions(
    conn: asyncpg.Connection,
    chat_ids: list[UUID] | None = None,
    limit: int = 20,
    offset: int = 0,
    bypass_mv: bool = False,
) -> list[GetAttemptChatCompletionResponse]:
    """Search attempt_chat_completion entries from attempt_chat_completion_mv with declarative filters."""
    source = await resolve_mv_source(conn, MV_NAME, bypass_mv)

    rows = await conn.fetch(
        f"""
        SELECT id, chat_id, stop, error, message, created_at, active, generated, mcp, call_id
        FROM {source}
        WHERE ($1::uuid[] IS NULL OR chat_id = ANY($1))
        ORDER BY created_at DESC
        LIMIT $2 OFFSET $3
        """,
        chat_ids,
        limit,
        offset,
    )

    return [GetAttemptChatCompletionResponse(**dict(r)) for r in rows]
