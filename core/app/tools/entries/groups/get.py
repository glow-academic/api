"""Groups GET — batch get from groups_mv."""

from uuid import UUID

import asyncpg  # type: ignore
from redis.asyncio import Redis

from app.infra.docs.resolve_mv_source import resolve_mv_source
from app.tools.entries.groups.types import GetGroupResponse

MV_NAME = "groups_mv"


async def get_groups(
    conn: asyncpg.Connection,
    ids: list[UUID],
    redis: Redis,
    bypass_mv: bool = False,
) -> list[GetGroupResponse]:
    """Get groups by IDs from groups_mv."""
    if not ids:
        return []

    source = await resolve_mv_source(conn, MV_NAME, bypass_mv)

    rows = await conn.fetch(
        f"""
        SELECT group_id, session_id, created_at, name, active, mcp, generated, artifact_type
        FROM {source}
        WHERE group_id = ANY($1)
        """,
        ids,
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
            artifact_type=r["artifact_type"],
        )
        for r in rows
    ]
