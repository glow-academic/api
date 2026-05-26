"""grants/get — reusable data-access layer."""

from uuid import UUID

import asyncpg  # type: ignore
from redis.asyncio import Redis

from app.tools.entries.grants.types import GetGrantResponse
from app.utils.cache.hedged_row import read_back_row

MV_NAME = "grants_mv"


async def get_grants(
    conn: asyncpg.Connection,
    ids: list[UUID],
    redis: Redis,
    *,
    bypass_cache: bool = False,
) -> list[GetGrantResponse]:
    """Get grant entries by IDs from grants_mv."""
    if not ids:
        return []

    cached_results: dict[str, GetGrantResponse] = {}
    missing_ids: list[UUID] = []
    if not bypass_cache:
        for gid in ids:
            cached = await read_back_row(redis, "grants", gid)
            if cached is not None:
                cached_results[str(gid)] = GetGrantResponse.model_validate(cached)
            else:
                missing_ids.append(gid)
    else:
        missing_ids = list(ids)

    mv_results: dict[str, GetGrantResponse] = {}
    if missing_ids:
        rows = await conn.fetch(
            f"""
            SELECT id, session_id, expires_at, created_at, active, generated, mcp, profiles_id
            FROM {MV_NAME}
            WHERE id = ANY($1)
            """,
            missing_ids,
        )
        for r in rows:
            mv_results[str(r["id"])] = GetGrantResponse(**dict(r))

    out: list[GetGrantResponse] = []
    for gid in ids:
        key = str(gid)
        if key in cached_results:
            out.append(cached_results[key])
        elif key in mv_results:
            out.append(mv_results[key])
    return out
