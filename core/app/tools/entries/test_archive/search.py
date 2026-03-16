"""Test archive search — filtered/paginated query against test_archive_mv."""

from uuid import UUID

import asyncpg  # type: ignore

from app.infra.docs.resolve_mv_source import resolve_mv_source
from app.tools.entries.test_archive.types import GetTestArchiveResponse

MV_NAME = "test_archive_mv"


async def search_test_archives(
    conn: asyncpg.Connection,
    test_ids: list[UUID] | None = None,
    limit: int = 20,
    offset: int = 0,
    bypass_mv: bool = False,
) -> list[GetTestArchiveResponse]:
    """Search test_archive entries from test_archive_mv with declarative filters."""
    source = await resolve_mv_source(conn, MV_NAME, bypass_mv)

    rows = await conn.fetch(
        f"""
        SELECT id, created_at, generated, mcp, active, test_id, archived, call_id
        FROM {source}
        WHERE ($1::uuid[] IS NULL OR test_id = ANY($1))
        ORDER BY created_at DESC
        LIMIT $2 OFFSET $3
        """,
        test_ids,
        limit,
        offset,
    )

    return [GetTestArchiveResponse(**dict(r)) for r in rows]
