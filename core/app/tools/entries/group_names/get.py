"""Group names GET — batch get from group_names_mv (latest name per group)."""

from uuid import UUID

import asyncpg  # type: ignore
from redis.asyncio import Redis

from app.infra.docs.resolve_mv_source import resolve_mv_source
from app.tools.entries.group_names.types import GetGroupNameResponse
from app.utils.cache.hedged_row import read_back_row

MV_NAME = "group_names_mv"


async def get_group_names(
    conn: asyncpg.Connection,
    group_ids: list[UUID],
    redis: Redis,
    bypass_mv: bool = False,
    *,
    bypass_cache: bool = False,
) -> list[GetGroupNameResponse]:
    """Get latest name per group from group_names_mv."""
    if not group_ids:
        return []

    cached_results: dict[str, GetGroupNameResponse] = {}
    missing_ids: list[UUID] = []
    if not bypass_cache:
        for gid in group_ids:
            cached = await read_back_row(redis, "group_names", gid)
            if cached is not None:
                cached_results[str(gid)] = GetGroupNameResponse.model_validate(cached)
            else:
                missing_ids.append(gid)
    else:
        missing_ids = list(group_ids)

    mv_results: dict[str, GetGroupNameResponse] = {}
    if missing_ids:
        source = await resolve_mv_source(conn, MV_NAME, bypass_mv)

        rows = await conn.fetch(
            f"""
            SELECT id, group_id, name, created_at, generated, mcp
            FROM {source}
            WHERE group_id = ANY($1)
            """,
            missing_ids,
        )

        for r in rows:
            mv_results[str(r["group_id"])] = GetGroupNameResponse(
                id=r["id"],
                group_id=r["group_id"],
                name=r["name"],
                created_at=r["created_at"],
                generated=r["generated"],
                mcp=r["mcp"],
            )

    out: list[GetGroupNameResponse] = []
    for gid in group_ids:
        key = str(gid)
        if key in cached_results:
            out.append(cached_results[key])
        elif key in mv_results:
            out.append(mv_results[key])
    return out
