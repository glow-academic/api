"""Problems search — filtered/paginated query against problems_mv."""

from datetime import datetime
from uuid import UUID

import asyncpg  # type: ignore

from app.infra.docs.resolve_mv_source import resolve_mv_source
from app.tools.entries.problems.types import GetProblemResponse

MV_NAME = "problems_mv"


async def search_problems(
    conn: asyncpg.Connection,
    profile_ids: list[UUID] | None = None,
    session_ids: list[UUID] | None = None,
    type: str | None = None,
    resolved: bool | None = None,
    date_from: datetime | None = None,
    date_to: datetime | None = None,
    mcp: bool | None = None,
    limit: int = 20,
    offset: int = 0,
    bypass_mv: bool = False,
) -> list[GetProblemResponse]:
    """Search problems from problems_mv with declarative filters."""
    source = await resolve_mv_source(conn, MV_NAME, bypass_mv)
    source_alias = "mv" if bypass_mv else "p"
    from_source = source if bypass_mv else f"{source} {source_alias}"

    rows = await conn.fetch(
        f"""
        SELECT {source_alias}.problem_id, {source_alias}.profile_id, c.session_id, {source_alias}.type, {source_alias}.message, {source_alias}.resolved, {source_alias}.created_at, {source_alias}.active, {source_alias}.mcp, {source_alias}.generated
        FROM {from_source}
        JOIN problems_entry pe ON pe.id = {source_alias}.problem_id
        LEFT JOIN calls_entry c ON c.id = pe.call_id
        WHERE ($1::uuid[] IS NULL OR {source_alias}.profile_id = ANY($1))
          AND ($2::uuid[] IS NULL OR c.session_id = ANY($2))
          AND ($3::text IS NULL OR {source_alias}.type = $3)
          AND ($4::boolean IS NULL OR {source_alias}.resolved = $4)
          AND ($5::timestamptz IS NULL OR {source_alias}.created_at >= $5)
          AND ($6::timestamptz IS NULL OR {source_alias}.created_at <= $6)
          AND ($7::boolean IS NULL OR {source_alias}.mcp = $7)
        ORDER BY {source_alias}.created_at DESC
        LIMIT $8 OFFSET $9
        """,
        profile_ids,
        session_ids,
        type,
        resolved,
        date_from,
        date_to,
        mcp,
        limit,
        offset,
    )

    return [
        GetProblemResponse(
            id=r["problem_id"],
            profile_id=r["profile_id"],
            session_id=r["session_id"],
            type=r["type"],
            message=r["message"],
            resolved=r["resolved"],
            created_at=r["created_at"],
            active=r["active"],
            mcp=r["mcp"],
            generated=r["generated"],
        )
        for r in rows
    ]
