"""Attempt strength search — filtered/paginated query against attempt_strength_mv."""

from uuid import UUID

import asyncpg  # type: ignore

from app.infra.docs.resolve_mv_source import resolve_mv_source
from app.tools.entries.attempt_strength.types import (
    GetAttemptStrengthResponse,
)

MV_NAME = "attempt_strength_mv"


async def search_attempt_strengths(
    conn: asyncpg.Connection,
    message_ids: list[UUID] | None = None,
    grade_ids: list[UUID] | None = None,
    limit: int = 20,
    offset: int = 0,
    bypass_mv: bool = False,
) -> list[GetAttemptStrengthResponse]:
    """Search attempt_strength entries from attempt_strength_mv with declarative filters."""
    source = await resolve_mv_source(conn, MV_NAME, bypass_mv)

    rows = await conn.fetch(
        f"""
        SELECT strength_id, message_id, grade_id, name, description, created_at
        FROM {source}
        WHERE ($1::uuid[] IS NULL OR message_id = ANY($1))
          AND ($2::uuid[] IS NULL OR grade_id = ANY($2))
        ORDER BY created_at DESC
        LIMIT $3 OFFSET $4
        """,
        message_ids,
        grade_ids,
        limit,
        offset,
    )

    return [GetAttemptStrengthResponse(**dict(r)) for r in rows]
