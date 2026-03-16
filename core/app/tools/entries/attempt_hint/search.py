"""Attempt hint search — filtered/paginated query against attempt_hint_mv."""

from uuid import UUID

import asyncpg  # type: ignore

from app.infra.docs.resolve_mv_source import resolve_mv_source
from app.tools.entries.attempt_hint.types import GetAttemptHintResponse

MV_NAME = "attempt_hint_mv"


async def search_attempt_hints(
    conn: asyncpg.Connection,
    message_ids: list[UUID] | None = None,
    limit: int = 20,
    offset: int = 0,
    bypass_mv: bool = False,
) -> list[GetAttemptHintResponse]:
    """Search attempt hints from attempt_hint_mv with declarative filters."""
    source = await resolve_mv_source(conn, MV_NAME, bypass_mv)

    rows = await conn.fetch(
        f"""
        SELECT hint_id, message_id, hint, idx, created_at
        FROM {source}
        WHERE ($1::uuid[] IS NULL OR message_id = ANY($1))
        ORDER BY created_at DESC
        LIMIT $2 OFFSET $3
        """,
        message_ids,
        limit,
        offset,
    )

    return [GetAttemptHintResponse(**dict(r)) for r in rows]
