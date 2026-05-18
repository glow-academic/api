"""Sessions search — filtered/paginated query against sessions_mv."""

from datetime import datetime
from uuid import UUID

import asyncpg  # type: ignore

from app.infra.docs.resolve_mv_source import resolve_mv_source
from app.tools.entries.sessions.types import GetSessionResponse

MV_NAME = "sessions_mv"


async def search_sessions(
    conn: asyncpg.Connection,
    profile_ids: list[UUID] | None = None,
    date_from: datetime | None = None,
    date_to: datetime | None = None,
    active: bool | None = None,
    mcp: bool | None = None,
    limit: int = 20,
    offset: int = 0,
    bypass_mv: bool = False,
) -> list[GetSessionResponse]:
    """Search sessions from sessions_mv with declarative filters."""
    source = await resolve_mv_source(conn, MV_NAME, bypass_mv)

    rows = await conn.fetch(
        f"""
        SELECT session_id, profile_id, session_created_at, active, mcp
        FROM {source}
        WHERE ($1::uuid[] IS NULL OR profile_id = ANY($1))
          AND ($2::timestamptz IS NULL OR session_created_at >= $2)
          AND ($3::timestamptz IS NULL OR session_created_at <= $3)
          AND ($4::boolean IS NULL OR active = $4)
          AND ($5::boolean IS NULL OR mcp = $5)
        ORDER BY session_created_at DESC
        LIMIT $6 OFFSET $7
        """,
        profile_ids,
        date_from,
        date_to,
        active,
        mcp,
        limit,
        offset,
    )

    return [
        GetSessionResponse(
            id=r["session_id"],
            profile_id=r["profile_id"],
            created_at=r["session_created_at"],
            active=r["active"],
            mcp=r["mcp"],
        )
        for r in rows
    ]
