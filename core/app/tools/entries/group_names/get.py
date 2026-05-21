"""Group names GET — batch get from group_names_mv (latest name per group)."""

from uuid import UUID

import asyncpg  # type: ignore
from redis.asyncio import Redis

from app.infra.docs.resolve_mv_source import resolve_mv_source
from app.tools.entries.group_names.types import GetGroupNameResponse

MV_NAME = "group_names_mv"


async def get_group_names(
    conn: asyncpg.Connection,
    group_ids: list[UUID],
    redis: Redis,
    bypass_mv: bool = False,
) -> list[GetGroupNameResponse]:
    """Get latest name per group from group_names_mv."""
    if not group_ids:
        return []

    source = await resolve_mv_source(conn, MV_NAME, bypass_mv)

    rows = await conn.fetch(
        f"""
        SELECT id, group_id, name, created_at, generated, mcp
        FROM {source}
        WHERE group_id = ANY($1)
        """,
        group_ids,
    )

    return [
        GetGroupNameResponse(
            id=r["id"],
            group_id=r["group_id"],
            name=r["name"],
            created_at=r["created_at"],
            generated=r["generated"],
            mcp=r["mcp"],
        )
        for r in rows
    ]
