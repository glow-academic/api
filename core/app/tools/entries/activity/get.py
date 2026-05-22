"""Activity GET — batch get from activity_mv."""

from uuid import UUID

import asyncpg  # type: ignore
from redis.asyncio import Redis

from app.infra.docs.resolve_mv_source import resolve_mv_source
from app.tools.entries.activity.types import GetActivityResponse
from app.utils.cache.hedged_row import read_back_row

MV_NAME = "activity_mv"


async def get_activity(
    conn: asyncpg.Connection,
    ids: list[UUID],
    redis: Redis,
    bypass_mv: bool = False,
    *,
    bypass_cache: bool = False,
) -> list[GetActivityResponse]:
    """Get activity entries by IDs from activity_mv."""
    if not ids:
        return []

    cached_results: dict[str, GetActivityResponse] = {}
    missing_ids: list[UUID] = []
    if not bypass_cache:
        for aid in ids:
            cached = await read_back_row(redis, "activity", aid)
            if cached is not None:
                cached_results[str(aid)] = GetActivityResponse.model_validate(cached)
            else:
                missing_ids.append(aid)
    else:
        missing_ids = list(ids)

    mv_results: dict[str, GetActivityResponse] = {}
    if missing_ids:
        source = await resolve_mv_source(conn, MV_NAME, bypass_mv)
        rows = await conn.fetch(
            f"""
            SELECT activity_id, profile_id, session_id, created_at, active, mcp, generated
            FROM {source}
            WHERE activity_id = ANY($1)
            """,
            missing_ids,
        )
        for r in rows:
            mv_results[str(r["activity_id"])] = GetActivityResponse(
                id=r["activity_id"],
                profile_id=r["profile_id"],
                session_id=r["session_id"],
                created_at=r["created_at"],
                active=r["active"],
                mcp=r["mcp"],
                generated=r["generated"],
            )

    out: list[GetActivityResponse] = []
    for aid in ids:
        key = str(aid)
        if key in cached_results:
            out.append(cached_results[key])
        elif key in mv_results:
            out.append(mv_results[key])
    return out
