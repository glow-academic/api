"""Attempt practice search — filtered/paginated query against attempt_practice_mv."""

from uuid import UUID

import asyncpg  # type: ignore

from app.infra.docs.resolve_mv_source import resolve_mv_source
from app.tools.entries.attempt_practice.types import (
    GetAttemptPracticeResponse,
)

MV_NAME = "attempt_practice_mv"


async def search_attempt_practice_entries(
    conn: asyncpg.Connection,
    attempt_ids: list[UUID] | None = None,
    practice_ids: list[UUID] | None = None,
    limit: int = 20,
    offset: int = 0,
    bypass_mv: bool = False,
) -> list[GetAttemptPracticeResponse]:
    """Search attempt_practice entries from attempt_practice_mv with declarative filters."""
    source = await resolve_mv_source(conn, MV_NAME, bypass_mv)

    rows = await conn.fetch(
        f"""
        SELECT attempt_id, practice_id, created_at, active, generated, mcp, session_id
        FROM {source}
        WHERE ($1::uuid[] IS NULL OR attempt_id = ANY($1))
          AND ($2::uuid[] IS NULL OR practice_id = ANY($2))
        ORDER BY created_at DESC
        LIMIT $3 OFFSET $4
        """,
        attempt_ids,
        practice_ids,
        limit,
        offset,
    )

    return [GetAttemptPracticeResponse(**dict(r)) for r in rows]
