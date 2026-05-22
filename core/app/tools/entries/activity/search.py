"""Activity search — filtered/paginated query against activity_mv."""

from datetime import datetime
from uuid import UUID

import asyncpg  # type: ignore
from redis.asyncio import Redis

from datetime import datetime as _dt

from app.infra.docs.resolve_mv_source import resolve_mv_source
from app.tools.entries.activity.types import GetActivityResponse
from app.utils.cache.hedged_row import hedged_search

MV_NAME = "activity_mv"


async def search_activity(
    conn: asyncpg.Connection,
    redis: Redis,
    profile_ids: list[UUID] | None = None,
    session_ids: list[UUID] | None = None,
    date_from: datetime | None = None,
    date_to: datetime | None = None,
    mcp: bool | None = None,
    limit: int = 20,
    offset: int = 0,
    bypass_mv: bool = False,
    bypass_cache: bool = False,
) -> list[GetActivityResponse]:
    """Search activity from activity_mv with declarative filters."""
    source = await resolve_mv_source(conn, MV_NAME, bypass_mv)

    rows = await conn.fetch(
        f"""
        SELECT activity_id, profile_id, session_id, created_at, active, mcp, generated
        FROM {source}
        WHERE ($1::uuid[] IS NULL OR profile_id = ANY($1))
          AND ($2::uuid[] IS NULL OR session_id = ANY($2))
          AND ($3::timestamptz IS NULL OR created_at >= $3)
          AND ($4::timestamptz IS NULL OR created_at <= $4)
          AND ($5::boolean IS NULL OR mcp = $5)
        ORDER BY created_at DESC
        LIMIT $6 OFFSET $7
        """,
        profile_ids,
        session_ids,
        date_from,
        date_to,
        mcp,
        limit + offset + 1000,
        0,
    )

    mv_dicts = [
        {
            "id": str(r["activity_id"]),
            "profile_id": str(r["profile_id"]) if r["profile_id"] else None,
            "session_id": str(r["session_id"]) if r["session_id"] else None,
            "created_at": r["created_at"],
            "active": r["active"],
            "mcp": r["mcp"],
            "generated": r["generated"],
        }
        for r in rows
    ]

    profile_ids_str = {str(p) for p in profile_ids} if profile_ids else None
    session_ids_str = {str(s) for s in session_ids} if session_ids else None

    def _parse_ts(ts):
        if isinstance(ts, str):
            return _dt.fromisoformat(ts)
        return ts

    def matches(row: dict) -> bool:
        if profile_ids_str is not None and str(row.get("profile_id")) not in profile_ids_str:
            return False
        if session_ids_str is not None and str(row.get("session_id")) not in session_ids_str:
            return False
        ts = _parse_ts(row.get("created_at"))
        if date_from is not None and (ts is None or ts < date_from):
            return False
        if date_to is not None and (ts is None or ts > date_to):
            return False
        if mcp is not None and row.get("mcp") != mcp:
            return False
        return True

    merged = await hedged_search(
        redis,
        "activity",
        mv_rows=mv_dicts,
        matches_filter=matches,
        limit=limit,
        offset=offset,
        bypass_cache=bypass_cache,
    )
    return [GetActivityResponse.model_validate(r) for r in merged]
