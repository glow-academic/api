"""Resolves search — filtered/paginated query against resolves_mv."""

from datetime import datetime
from uuid import UUID

import asyncpg  # type: ignore

from app.infra.docs.resolve_mv_source import resolve_mv_source
from app.tools.entries.resolves.types import GetResolveResponse

MV_NAME = "resolves_mv"


async def search_resolves(
    conn: asyncpg.Connection,
    problem_ids: list[UUID] | None = None,
    call_ids: list[UUID] | None = None,
    resolved: bool | None = None,
    date_from: datetime | None = None,
    date_to: datetime | None = None,
    mcp: bool | None = None,
    limit: int = 20,
    offset: int = 0,
    bypass_mv: bool = False,
) -> list[GetResolveResponse]:
    """Search resolves from resolves_mv with declarative filters."""
    source = await resolve_mv_source(conn, MV_NAME, bypass_mv)

    rows = await conn.fetch(
        f"""
        SELECT id, created_at, generated, mcp, active, problem_id, resolved, call_id
        FROM {source}
        WHERE ($1::uuid[] IS NULL OR problem_id = ANY($1))
          AND ($2::uuid[] IS NULL OR call_id = ANY($2))
          AND ($3::boolean IS NULL OR resolved = $3)
          AND ($4::timestamptz IS NULL OR created_at >= $4)
          AND ($5::timestamptz IS NULL OR created_at <= $5)
          AND ($6::boolean IS NULL OR mcp = $6)
        ORDER BY created_at DESC
        LIMIT $7 OFFSET $8
        """,
        problem_ids,
        call_ids,
        resolved,
        date_from,
        date_to,
        mcp,
        limit,
        offset,
    )

    return [
        GetResolveResponse(
            id=r["id"],
            created_at=r["created_at"],
            generated=r["generated"],
            mcp=r["mcp"],
            active=r["active"],
            problem_id=r["problem_id"],
            resolved=r["resolved"],
            call_id=r["call_id"],
        )
        for r in rows
    ]
