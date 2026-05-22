"""Groups GET — batch get from groups_mv."""

from uuid import UUID

import asyncpg  # type: ignore
from redis.asyncio import Redis

from app.infra.docs.resolve_mv_source import resolve_mv_source
from app.tools.entries.groups.types import GetGroupResponse
from app.utils.cache.hedged_row import read_back_row

MV_NAME = "groups_mv"


async def get_groups(
    conn: asyncpg.Connection,
    ids: list[UUID],
    redis: Redis,
    bypass_mv: bool = False,
    *,
    bypass_cache: bool = False,
) -> list[GetGroupResponse]:
    """Get groups by IDs from groups_mv."""
    if not ids:
        return []

    cached_results: dict[str, GetGroupResponse] = {}
    missing_ids: list[UUID] = []
    if not bypass_cache:
        for gid in ids:
            cached = await read_back_row(redis, "groups", gid)
            if cached is not None:
                cached_results[str(gid)] = GetGroupResponse.model_validate(cached)
            else:
                missing_ids.append(gid)
    else:
        missing_ids = list(ids)

    mv_results: dict[str, GetGroupResponse] = {}
    if missing_ids:
        source = await resolve_mv_source(conn, MV_NAME, bypass_mv)
        rows = await conn.fetch(
            f"""
            SELECT group_id, session_id, created_at, name, active, mcp, generated, artifact_type
            FROM {source}
            WHERE group_id = ANY($1)
            """,
            missing_ids,
        )
        for r in rows:
            mv_results[str(r["group_id"])] = GetGroupResponse(
                id=r["group_id"],
                session_id=r["session_id"],
                created_at=r["created_at"],
                name=r["name"],
                active=r["active"],
                mcp=r["mcp"],
                generated=r["generated"],
                artifact_type=r["artifact_type"],
            )

    out: list[GetGroupResponse] = []
    for gid in ids:
        key = str(gid)
        if key in cached_results:
            out.append(cached_results[key])
        elif key in mv_results:
            out.append(mv_results[key])
    return out
