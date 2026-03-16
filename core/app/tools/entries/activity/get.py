"""Activity GET — batch get from activity_mv."""

from uuid import UUID

import asyncpg  # type: ignore

from app.infra.docs.resolve_mv_source import resolve_mv_source
from app.tools.entries.activity.types import GetActivityResponse

MV_NAME = "activity_mv"


async def get_activity(
    conn: asyncpg.Connection,
    ids: list[UUID],
    bypass_mv: bool = False,
) -> list[GetActivityResponse]:
    """Get activity entries by IDs from activity_mv."""
    if not ids:
        return []

    source = await resolve_mv_source(conn, MV_NAME, bypass_mv)

    rows = await conn.fetch(
        f"""
        SELECT activity_id, profile_id, session_id, created_at, active, mcp, generated
        FROM {source}
        WHERE activity_id = ANY($1)
        """,
        ids,
    )

    return [
        GetActivityResponse(
            id=r["activity_id"],
            profile_id=r["profile_id"],
            session_id=r["session_id"],
            created_at=r["created_at"],
            active=r["active"],
            mcp=r["mcp"],
            generated=r["generated"],
        )
        for r in rows
    ]
