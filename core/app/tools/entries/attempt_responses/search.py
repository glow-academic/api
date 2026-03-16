"""Attempt responses search — filtered/paginated query against attempt_responses_mv."""

from uuid import UUID

import asyncpg  # type: ignore

from app.infra.docs.resolve_mv_source import resolve_mv_source
from app.tools.entries.attempt_responses.types import (
    GetAttemptResponsesResponse,
)

MV_NAME = "attempt_responses_mv"


async def search_attempt_responses(
    conn: asyncpg.Connection,
    chat_ids: list[UUID] | None = None,
    question_ids: list[UUID] | None = None,
    option_ids: list[UUID] | None = None,
    limit: int = 20,
    offset: int = 0,
    bypass_mv: bool = False,
) -> list[GetAttemptResponsesResponse]:
    """Search attempt_responses entries from attempt_responses_mv with declarative filters."""
    source = await resolve_mv_source(conn, MV_NAME, bypass_mv)

    rows = await conn.fetch(
        f"""
        SELECT response_id, chat_id, question_id, option_id, created_at
        FROM {source}
        WHERE ($1::uuid[] IS NULL OR chat_id = ANY($1))
          AND ($2::uuid[] IS NULL OR question_id = ANY($2))
          AND ($3::uuid[] IS NULL OR option_id = ANY($3))
        ORDER BY created_at DESC
        LIMIT $4 OFFSET $5
        """,
        chat_ids,
        question_ids,
        option_ids,
        limit,
        offset,
    )

    return [GetAttemptResponsesResponse(**dict(r)) for r in rows]
