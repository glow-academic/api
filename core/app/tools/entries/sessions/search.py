"""Sessions search — filtered/paginated query against sessions_mv."""

from datetime import datetime
from uuid import UUID

import asyncpg  # type: ignore
from redis.asyncio import Redis

from datetime import datetime as _dt

from app.infra.docs.resolve_mv_source import resolve_mv_source
from app.tools.entries.sessions.types import GetSessionResponse
from app.utils.cache.hedged_row import hedged_search

MV_NAME = "sessions_mv"


async def search_sessions(
    conn: asyncpg.Connection,
    redis: Redis,
    profile_ids: list[UUID] | None = None,
    date_from: datetime | None = None,
    date_to: datetime | None = None,
    active: bool | None = None,
    mcp: bool | None = None,
    limit: int = 20,
    offset: int = 0,
    bypass_mv: bool = False,
    bypass_cache: bool = False,
) -> list[GetSessionResponse]:
    """Search sessions from sessions_mv with declarative filters."""
    source = await resolve_mv_source(conn, MV_NAME, bypass_mv)

    rows = await conn.fetch(
        f"""
        SELECT session_id, profile_id, session_created_at, active, mcp
        FROM {source}
        WHERE ($1::uuid[] IS NULL OR profile_id = ANY($1))
          AND ($2::timestamptz IS NULL OR session_created_at >= $2)
          AND ($3::timestamptz IS NULL OR session_created_at <= $3)
          AND ($4::boolean IS NULL OR active = $4)
          AND ($5::boolean IS NULL OR mcp = $5)
        ORDER BY session_created_at DESC, session_id
        LIMIT $6 OFFSET $7
        """,
        profile_ids,
        date_from,
        date_to,
        active,
        mcp,
        limit + offset + 1000,
        0,
    )

    mv_dicts = [
        {
            "id": str(r["session_id"]),
            "profile_id": str(r["profile_id"]) if r["profile_id"] else None,
            "created_at": r["session_created_at"],
            "active": r["active"],
            "mcp": r["mcp"],
        }
        for r in rows
    ]

    profile_ids_str = {str(p) for p in profile_ids} if profile_ids else None

    def _parse_ts(ts):
        if isinstance(ts, str):
            return _dt.fromisoformat(ts)
        return ts

    def matches(row: dict) -> bool:
        if profile_ids_str is not None and str(row.get("profile_id")) not in profile_ids_str:
            return False
        ts = _parse_ts(row.get("created_at"))
        if date_from is not None and (ts is None or ts < date_from):
            return False
        if date_to is not None and (ts is None or ts > date_to):
            return False
        if active is not None and row.get("active") != active:
            return False
        if mcp is not None and row.get("mcp") != mcp:
            return False
        return True

    # Deterministic pagination (P2): the merge-sort tiebreaks on a non-unique
    # ``created_at`` exactly like the SQL ORDER BY. Without a unique secondary
    # key, tied timestamps order arbitrarily between calls (cache+MV inputs
    # arrive in different orders), so a session could dup/skip across pages.
    # Tiebreak on the id — mirrors ``ORDER BY session_created_at DESC,
    # session_id`` above so cache rows and MV rows order identically.
    def _sort_key(row: dict) -> tuple:
        ts = _parse_ts(row.get("created_at"))
        return (ts or _dt.min, str(row.get("id") or ""))

    merged = await hedged_search(
        redis,
        "sessions",
        mv_rows=mv_dicts,
        matches_filter=matches,
        sort_key=_sort_key,
        limit=limit,
        offset=offset,
        bypass_cache=bypass_cache,
    )
    return [GetSessionResponse.model_validate(r) for r in merged]
