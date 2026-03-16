"""Calls search — filtered/paginated query against calls_mv."""

from uuid import UUID

import asyncpg  # type: ignore

from app.infra.docs.resolve_mv_source import resolve_mv_source
from app.tools.entries.calls.types import SearchCallResponse

MV_NAME = "calls_mv"


async def search_calls(
    conn: asyncpg.Connection,
    run_ids: list[UUID] | None = None,
    tool_ids: list[UUID] | None = None,
    limit: int = 20,
    offset: int = 0,
    bypass_mv: bool = False,
) -> list[SearchCallResponse]:
    """Search calls from calls_mv with declarative filters."""
    source = await resolve_mv_source(conn, MV_NAME, bypass_mv)

    rows = await conn.fetch(
        f"""
        SELECT call_id, run_id, call_created_at,
               upload_id, file_path, mime_type, tool_id
        FROM {source}
        WHERE ($1::uuid[] IS NULL OR run_id = ANY($1))
          AND ($2::uuid[] IS NULL OR tool_id = ANY($2))
        ORDER BY call_created_at DESC
        LIMIT $3 OFFSET $4
        """,
        run_ids,
        tool_ids,
        limit,
        offset,
    )

    return [SearchCallResponse(**dict(r)) for r in rows]
