"""Groups search — filtered/paginated query against groups_mv."""

from datetime import datetime
from uuid import UUID

import asyncpg  # type: ignore

from app.infra.docs.resolve_mv_source import resolve_mv_source
from app.tools.entries.groups.types import GetGroupResponse

MV_NAME = "groups_mv"


async def search_groups(
    conn: asyncpg.Connection,
    session_ids: list[UUID] | None = None,
    name: str | None = None,
    date_from: datetime | None = None,
    date_to: datetime | None = None,
    mcp: bool | None = None,
    limit: int = 20,
    offset: int = 0,
    bypass_mv: bool = False,
) -> list[GetGroupResponse]:
    """Search groups from groups_mv with declarative filters."""
    source = await resolve_mv_source(conn, MV_NAME, bypass_mv)

    rows = await conn.fetch(
        f"""
        SELECT group_id, session_id, created_at, name, active, mcp, generated
        FROM {source}
        WHERE ($1::uuid[] IS NULL OR session_id = ANY($1))
          AND ($2::text IS NULL OR name ILIKE '%' || $2 || '%')
          AND ($3::timestamptz IS NULL OR created_at >= $3)
          AND ($4::timestamptz IS NULL OR created_at <= $4)
          AND ($5::boolean IS NULL OR mcp = $5)
        ORDER BY created_at DESC
        LIMIT $6 OFFSET $7
        """,
        session_ids,
        name,
        date_from,
        date_to,
        mcp,
        limit,
        offset,
    )

    return [
        GetGroupResponse(
            id=r["group_id"],
            session_id=r["session_id"],
            created_at=r["created_at"],
            name=r["name"],
            active=r["active"],
            mcp=r["mcp"],
            generated=r["generated"],
        )
        for r in rows
    ]
