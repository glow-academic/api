"""Attempt message completion search — filtered/paginated query against attempt_message_completion_mv."""

from datetime import datetime
from uuid import UUID

import asyncpg  # type: ignore
from pydantic import BaseModel

from app.infra.docs.resolve_mv_source import resolve_mv_source

MV_NAME = "attempt_message_completion_mv"


class GetAttemptMessageCompletionResponse(BaseModel):
    id: UUID
    attempt_message_id: UUID
    stop: bool
    error: bool
    message: str
    call_id: UUID
    created_at: datetime
    active: bool
    generated: bool
    mcp: bool


async def search_attempt_message_completions(
    conn: asyncpg.Connection,
    attempt_message_ids: list[UUID] | None = None,
    limit: int = 20,
    offset: int = 0,
    bypass_mv: bool = False,
) -> list[GetAttemptMessageCompletionResponse]:
    """Search attempt_message_completion entries with declarative filters."""
    source = await resolve_mv_source(conn, MV_NAME, bypass_mv)

    rows = await conn.fetch(
        f"""
        SELECT id, attempt_message_id, stop, error, message, call_id, created_at, active, generated, mcp
        FROM {source}
        WHERE ($1::uuid[] IS NULL OR attempt_message_id = ANY($1))
        ORDER BY created_at DESC
        LIMIT $2 OFFSET $3
        """,
        attempt_message_ids,
        limit,
        offset,
    )

    return [GetAttemptMessageCompletionResponse(**dict(r)) for r in rows]
