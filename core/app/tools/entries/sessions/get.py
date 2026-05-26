"""Sessions GET — batch get from sessions_mv."""

from uuid import UUID

import asyncpg  # type: ignore
from redis.asyncio import Redis

from app.infra.docs.resolve_mv_source import resolve_mv_source
from app.tools.entries.sessions.types import GetSessionResponse
from app.utils.cache.hedged_row import read_back_row

MV_NAME = "sessions_mv"


async def get_sessions(
    conn: asyncpg.Connection,
    ids: list[UUID],
    redis: Redis,
    bypass_mv: bool = False,
    *,
    bypass_cache: bool = False,
) -> list[GetSessionResponse]:
    """Get sessions by IDs from sessions_mv (with cache hedge)."""
    if not ids:
        return []

    cached_results: dict[str, GetSessionResponse] = {}
    missing_ids: list[UUID] = []
    if not bypass_cache:
        for sid in ids:
            cached = await read_back_row(redis, "sessions", sid)
            if cached is not None:
                cached_results[str(sid)] = GetSessionResponse.model_validate(cached)
            else:
                missing_ids.append(sid)
    else:
        missing_ids = list(ids)

    mv_results: dict[str, GetSessionResponse] = {}
    if missing_ids:
        source = await resolve_mv_source(conn, MV_NAME, bypass_mv)
        rows = await conn.fetch(
            f"""
            SELECT session_id, profile_id, session_created_at, active, mcp
            FROM {source}
            WHERE session_id = ANY($1)
            """,
            missing_ids,
        )
        for r in rows:
            mv_results[str(r["session_id"])] = GetSessionResponse(
                id=r["session_id"],
                profile_id=r["profile_id"],
                created_at=r["session_created_at"],
                active=r["active"],
                mcp=r["mcp"],
            )

    out: list[GetSessionResponse] = []
    for sid in ids:
        key = str(sid)
        if key in cached_results:
            out.append(cached_results[key])
        elif key in mv_results:
            out.append(mv_results[key])
    return out
