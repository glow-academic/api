"""Attempt replacement search — filtered/paginated query against attempt_replacement_mv."""

from uuid import UUID

import asyncpg  # type: ignore

from app.infra.docs.resolve_mv_source import resolve_mv_source
from app.tools.entries.attempt_replacement.types import (
    GetAttemptReplacementResponse,
)

MV_NAME = "attempt_replacement_mv"


async def search_attempt_replacements(
    conn: asyncpg.Connection,
    improvement_ids: list[UUID] | None = None,
    limit: int = 20,
    offset: int = 0,
    bypass_mv: bool = False,
) -> list[GetAttemptReplacementResponse]:
    """Search attempt_replacement entries from attempt_replacement_mv with declarative filters."""
    source = await resolve_mv_source(conn, MV_NAME, bypass_mv)

    rows = await conn.fetch(
        f"""
        SELECT replacement_id, improvement_id, section, replace_text, idx, created_at
        FROM {source}
        WHERE ($1::uuid[] IS NULL OR improvement_id = ANY($1))
        ORDER BY created_at DESC
        LIMIT $2 OFFSET $3
        """,
        improvement_ids,
        limit,
        offset,
    )

    return [GetAttemptReplacementResponse(**dict(r)) for r in rows]
