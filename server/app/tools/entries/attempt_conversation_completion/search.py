"""Attempt conversation completion search — filtered/paginated query against attempt_conversation_completion_mv."""

from uuid import UUID

import asyncpg  # type: ignore

from app.infra.docs.resolve_mv_source import resolve_mv_source
from app.tools.entries.attempt_conversation_completion.types import (
    GetAttemptConversationCompletionResponse,
)

MV_NAME = "attempt_conversation_completion_mv"


async def search_attempt_conversation_completions(
    conn: asyncpg.Connection,
    conversation_ids: list[UUID] | None = None,
    limit: int = 20,
    offset: int = 0,
    bypass_mv: bool = False,
) -> list[GetAttemptConversationCompletionResponse]:
    """Search attempt_conversation_completion entries with declarative filters."""
    source = await resolve_mv_source(conn, MV_NAME, bypass_mv)

    rows = await conn.fetch(
        f"""
        SELECT id, created_at, generated, mcp, active, conversation_id, stop, error, message, call_id
        FROM {source}
        WHERE ($1::uuid[] IS NULL OR conversation_id = ANY($1))
        ORDER BY created_at DESC
        LIMIT $2 OFFSET $3
        """,
        conversation_ids,
        limit,
        offset,
    )

    return [GetAttemptConversationCompletionResponse(**dict(r)) for r in rows]
