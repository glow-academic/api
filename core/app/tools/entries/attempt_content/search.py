"""Attempt content search — filtered/paginated query against attempt_content_mv."""

from uuid import UUID

import asyncpg  # type: ignore

from app.infra.docs.resolve_mv_source import resolve_mv_source
from app.tools.entries.attempt_content.types import GetAttemptContentResponse

MV_NAME = "attempt_content_mv"


async def search_attempt_contents(
    conn: asyncpg.Connection,
    message_ids: list[UUID] | None = None,
    persona_entry_ids: list[UUID] | None = None,
    limit: int = 20,
    offset: int = 0,
    bypass_mv: bool = False,
) -> list[GetAttemptContentResponse]:
    """Search attempt contents from attempt_content_mv with declarative filters."""
    source = await resolve_mv_source(conn, MV_NAME, bypass_mv)

    rows = await conn.fetch(
        f"""
        SELECT content_id, message_id, content, persona_entry_id, idx, created_at
        FROM {source}
        WHERE ($1::uuid[] IS NULL OR message_id = ANY($1))
          AND ($2::uuid[] IS NULL OR persona_entry_id = ANY($2))
        ORDER BY created_at DESC
        LIMIT $3 OFFSET $4
        """,
        message_ids,
        persona_entry_ids,
        limit,
        offset,
    )

    return [GetAttemptContentResponse(**dict(r)) for r in rows]
