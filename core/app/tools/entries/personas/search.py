"""Personas SEARCH — declarative filters on base table + connection."""

from datetime import datetime
from uuid import UUID

import asyncpg  # type: ignore
from redis.asyncio import Redis

from datetime import datetime as _dt

from app.tools.entries.personas.types import GetPersonasResponse
from app.utils.cache.hedged_row import hedged_search


async def search_personas(
    conn: asyncpg.Connection,
    redis: Redis,
    session_ids: list[UUID] | None = None,
    date_from: datetime | None = None,
    date_to: datetime | None = None,
    limit: int = 20,
    offset: int = 0,
    bypass_cache: bool = False,
) -> list[GetPersonasResponse]:
    """Search personas entries with declarative filters."""
    rows = await conn.fetch(
        """
        SELECT
            e.id, e.created_at, e.active, e.generated, e.mcp, e.session_id,
            COALESCE(ARRAY_AGG(DISTINCT pc.personas_id) FILTER (WHERE pc.personas_id IS NOT NULL), '{}') AS persona_ids
        FROM personas_entry e
        LEFT JOIN personas_personas_connection pc ON pc.personas_entry_id = e.id
        WHERE e.active = true
          AND ($1::uuid[] IS NULL OR e.session_id = ANY($1))
          AND ($2::timestamptz IS NULL OR e.created_at >= $2)
          AND ($3::timestamptz IS NULL OR e.created_at <= $3)
        GROUP BY e.id, e.created_at, e.active, e.generated, e.mcp, e.session_id
        ORDER BY e.created_at DESC
        LIMIT $4 OFFSET $5
        """,
        session_ids,
        date_from,
        date_to,
        limit + offset + 1000,
        0,
    )

    mv_dicts = [
        {
            "id": str(r["id"]),
            "created_at": r["created_at"],
            "active": r["active"],
            "generated": r["generated"],
            "mcp": r["mcp"],
            "session_id": str(r["session_id"]) if r["session_id"] else None,
            "persona_ids": [str(p) for p in r["persona_ids"]],
        }
        for r in rows
    ]

    session_ids_str = {str(s) for s in session_ids} if session_ids else None

    def _parse_ts(ts):
        if isinstance(ts, str):
            return _dt.fromisoformat(ts)
        return ts

    def matches(row: dict) -> bool:
        if not row.get("active", True):
            return False
        if session_ids_str is not None and str(row.get("session_id")) not in session_ids_str:
            return False
        ts = _parse_ts(row.get("created_at"))
        if date_from is not None and (ts is None or ts < date_from):
            return False
        if date_to is not None and (ts is None or ts > date_to):
            return False
        return True

    merged = await hedged_search(
        redis,
        "personas",
        mv_rows=mv_dicts,
        matches_filter=matches,
        limit=limit,
        offset=offset,
        bypass_cache=bypass_cache,
    )
    return [GetPersonasResponse.model_validate(r) for r in merged]
