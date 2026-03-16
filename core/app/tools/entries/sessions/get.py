"""Sessions GET — batch get from sessions_mv."""

from uuid import UUID

import asyncpg  # type: ignore

from app.infra.docs.resolve_mv_source import resolve_mv_source
from app.tools.entries.sessions.types import GetSessionResponse

MV_NAME = "sessions_mv"


async def get_sessions(
    conn: asyncpg.Connection,
    ids: list[UUID],
    bypass_mv: bool = False,
) -> list[GetSessionResponse]:
    """Get sessions by IDs from sessions_mv."""
    if not ids:
        return []

    source = await resolve_mv_source(conn, MV_NAME, bypass_mv)

    rows = await conn.fetch(
        f"""
        SELECT session_id, profile_id, session_created_at, active, mcp
        FROM {source}
        WHERE session_id = ANY($1)
        """,
        ids,
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
