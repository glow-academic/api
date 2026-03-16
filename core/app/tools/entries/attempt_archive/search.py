"""Attempt archive search — filtered/paginated query against attempt_archive_mv."""

from uuid import UUID

import asyncpg  # type: ignore

from app.infra.docs.resolve_mv_source import resolve_mv_source
from app.tools.entries.attempt_archive.types import GetAttemptArchiveResponse

MV_NAME = "attempt_archive_mv"


async def search_attempt_archives(
    conn: asyncpg.Connection,
    attempt_ids: list[UUID] | None = None,
    limit: int = 20,
    offset: int = 0,
    bypass_mv: bool = False,
) -> list[GetAttemptArchiveResponse]:
    """Search attempt_archive entries from attempt_archive_mv with declarative filters."""
    source = await resolve_mv_source(conn, MV_NAME, bypass_mv)

    rows = await conn.fetch(
        f"""
        SELECT id, created_at, generated, mcp, active, attempt_id, archived, call_id
        FROM {source}
        WHERE ($1::uuid[] IS NULL OR attempt_id = ANY($1))
        ORDER BY created_at DESC
        LIMIT $2 OFFSET $3
        """,
        attempt_ids,
        limit,
        offset,
    )

    return [GetAttemptArchiveResponse(**dict(r)) for r in rows]
