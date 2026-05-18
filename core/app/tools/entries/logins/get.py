"""Logins GET — batch get from logins_mv."""

from uuid import UUID

import asyncpg  # type: ignore

from app.infra.docs.resolve_mv_source import resolve_mv_source
from app.tools.entries.logins.types import GetLoginResponse

MV_NAME = "logins_mv"


async def get_logins(
    conn: asyncpg.Connection,
    ids: list[UUID],
    bypass_mv: bool = False,
) -> list[GetLoginResponse]:
    """Get logins by IDs from logins_mv."""
    if not ids:
        return []

    source = await resolve_mv_source(conn, MV_NAME, bypass_mv)

    rows = await conn.fetch(
        f"""
        SELECT login_id, profile_id, session_id, created_at, active, mcp, generated
        FROM {source}
        WHERE login_id = ANY($1)
        """,
        ids,
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
