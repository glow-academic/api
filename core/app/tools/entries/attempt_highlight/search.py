"""Attempt highlight search — filtered/paginated query against attempt_highlight_mv."""

from uuid import UUID

import asyncpg  # type: ignore

from app.infra.docs.resolve_mv_source import resolve_mv_source
from app.tools.entries.attempt_highlight.types import (
    GetAttemptHighlightResponse,
)

MV_NAME = "attempt_highlight_mv"


async def search_attempt_highlights(
    conn: asyncpg.Connection,
    strength_ids: list[UUID] | None = None,
    limit: int = 20,
    offset: int = 0,
    bypass_mv: bool = False,
) -> list[GetAttemptHighlightResponse]:
    """Search attempt_highlight entries from attempt_highlight_mv with declarative filters."""
    source = await resolve_mv_source(conn, MV_NAME, bypass_mv)

    rows = await conn.fetch(
        f"""
        SELECT highlight_id, strength_id, section, idx, created_at
        FROM {source}
        WHERE ($1::uuid[] IS NULL OR strength_id = ANY($1))
        ORDER BY created_at DESC
        LIMIT $2 OFFSET $3
        """,
        strength_ids,
        limit,
        offset,
    )

    return [GetAttemptHighlightResponse(**dict(r)) for r in rows]
