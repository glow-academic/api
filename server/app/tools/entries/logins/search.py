"""Logins search — filtered/paginated query against logins_mv."""

from datetime import datetime
from uuid import UUID

import asyncpg  # type: ignore

from app.infra.docs.resolve_mv_source import resolve_mv_source
from app.tools.entries.logins.types import GetLoginResponse

MV_NAME = "logins_mv"


async def search_logins(
    conn: asyncpg.Connection,
    profile_ids: list[UUID] | None = None,
    session_ids: list[UUID] | None = None,
    date_from: datetime | None = None,
    date_to: datetime | None = None,
    mcp: bool | None = None,
    limit: int = 20,
    offset: int = 0,
    bypass_mv: bool = False,
) -> list[GetLoginResponse]:
    """Search logins from logins_mv with declarative filters."""
    source = await resolve_mv_source(conn, MV_NAME, bypass_mv)

    rows = await conn.fetch(
        f"""
        SELECT login_id, profile_id, session_id, created_at, active, mcp, generated
        FROM {source}
        WHERE ($1::uuid[] IS NULL OR profile_id = ANY($1))
          AND ($2::uuid[] IS NULL OR session_id = ANY($2))
          AND ($3::timestamptz IS NULL OR created_at >= $3)
          AND ($4::timestamptz IS NULL OR created_at <= $4)
          AND ($5::boolean IS NULL OR mcp = $5)
        ORDER BY created_at DESC
        LIMIT $6 OFFSET $7
        """,
        profile_ids,
        session_ids,
        date_from,
        date_to,
        mcp,
        limit,
        offset,
    )

    return [
        GetLoginResponse(
            id=r["login_id"],
            profile_id=r["profile_id"],
            session_id=r["session_id"],
            created_at=r["created_at"],
            active=r["active"],
            mcp=r["mcp"],
            generated=r["generated"],
        )
        for r in rows
    ]
