"""Attempt home search — filtered/paginated query against attempt_home_mv."""

from uuid import UUID

import asyncpg  # type: ignore
from redis.asyncio import Redis

from app.infra.docs.resolve_mv_source import resolve_mv_source
from app.tools.entries.attempt_home.types import GetAttemptHomeResponse
from app.utils.cache.hedged_row import hedged_search

MV_NAME = "attempt_home_mv"


async def search_attempt_homes(
    conn: asyncpg.Connection,
    redis: Redis,
    attempt_ids: list[UUID] | None = None,
    home_ids: list[UUID] | None = None,
    session_ids: list[UUID] | None = None,
    limit: int = 20,
    offset: int = 0,
    bypass_mv: bool = False,
    bypass_cache: bool = False,
) -> list[GetAttemptHomeResponse]:
    """Search attempt_home entries from attempt_home_mv with declarative filters."""
    source = await resolve_mv_source(conn, MV_NAME, bypass_mv)

    rows = await conn.fetch(
        f"""
        SELECT attempt_id, home_id, created_at, active, generated, mcp, session_id
        FROM {source}
        WHERE ($1::uuid[] IS NULL OR attempt_id = ANY($1))
          AND ($2::uuid[] IS NULL OR home_id = ANY($2))
          AND ($3::uuid[] IS NULL OR session_id = ANY($3))
        ORDER BY created_at DESC
        LIMIT $4 OFFSET $5
        """,
        attempt_ids,
        home_ids,
        session_ids,
        limit + offset + 1000,
        0,
    )

    mv_dicts = [
        {
            "home_link_key": f"{r['attempt_id']}:{r['home_id']}",
            "attempt_id": str(r["attempt_id"]),
            "home_id": str(r["home_id"]),
            "created_at": r["created_at"],
            "active": r["active"],
            "generated": r["generated"],
            "mcp": r["mcp"],
            "session_id": str(r["session_id"]) if r["session_id"] else None,
        }
        for r in rows
    ]

    attempt_ids_str = {str(a) for a in attempt_ids} if attempt_ids else None
    home_ids_str = {str(h) for h in home_ids} if home_ids else None
    session_ids_str = {str(s) for s in session_ids} if session_ids else None

    def matches(row: dict) -> bool:
        if attempt_ids_str is not None and str(row.get("attempt_id")) not in attempt_ids_str:
            return False
        if home_ids_str is not None and str(row.get("home_id")) not in home_ids_str:
            return False
        if session_ids_str is not None and str(row.get("session_id")) not in session_ids_str:
            return False
        if not row.get("active", True):
            return False
        return True

    merged = await hedged_search(
        redis,
        "attempt_home",
        mv_rows=mv_dicts,
        matches_filter=matches,
        limit=limit,
        offset=offset,
        id_key="home_link_key",
        bypass_cache=bypass_cache,
    )
    return [
        GetAttemptHomeResponse.model_validate(
            {k: v for k, v in r.items() if k != "home_link_key"}
        )
        for r in merged
    ]
