"""Logouts GET — batch get from logouts_mv."""

from uuid import UUID

import asyncpg  # type: ignore

from app.infra.docs.resolve_mv_source import resolve_mv_source
from app.tools.entries.logouts.types import GetLogoutResponse

MV_NAME = "logouts_mv"


async def get_logouts(
    conn: asyncpg.Connection,
    ids: list[UUID],
    bypass_mv: bool = False,
) -> list[GetLogoutResponse]:
    """Get logouts by IDs from logouts_mv."""
    if not ids:
        return []

    source = await resolve_mv_source(conn, MV_NAME, bypass_mv)

    rows = await conn.fetch(
        f"""
        SELECT logout_id, profile_id, session_id, created_at, active, mcp, generated
        FROM {source}
        WHERE logout_id = ANY($1)
        """,
        ids,
    )

    return [
        GetLogoutResponse(
            id=r["logout_id"],
            profile_id=r["profile_id"],
            session_id=r["session_id"],
            created_at=r["created_at"],
            active=r["active"],
            mcp=r["mcp"],
            generated=r["generated"],
        )
        for r in rows
    ]
