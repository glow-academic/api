"""Grants search — filtered/paginated query against grants_mv."""

from uuid import UUID

import asyncpg  # type: ignore
from redis.asyncio import Redis

from app.infra.docs.resolve_mv_source import resolve_mv_source
from app.tools.entries.grants.types import GetGrantResponse
from app.utils.cache.hedged_row import hedged_search

MV_NAME = "grants_mv"


async def search_grants(
    conn: asyncpg.Connection,
    redis: Redis,
    session_ids: list[UUID] | None = None,
    profiles_ids: list[UUID] | None = None,
    active: bool | None = None,
    limit: int = 20,
    offset: int = 0,
    bypass_mv: bool = False,
    bypass_cache: bool = False,
) -> list[GetGrantResponse]:
    """Search grants from grants_mv with declarative filters."""
    source = await resolve_mv_source(conn, MV_NAME, bypass_mv)

    rows = await conn.fetch(
        f"""
        SELECT id, session_id, expires_at, created_at, active, generated, mcp, profiles_id
        FROM {source}
        WHERE ($1::uuid[] IS NULL OR session_id = ANY($1))
          AND ($4::uuid[] IS NULL OR profiles_id = ANY($4))
          AND ($5::boolean IS NULL OR active = $5)
        ORDER BY created_at DESC
        LIMIT $2 OFFSET $3
        """,
        session_ids,
        limit + offset + 1000,
        0,
        profiles_ids,
        active,
    )

    mv_dicts = [
        {
            "id": str(r["id"]),
            "session_id": str(r["session_id"]),
            "expires_at": r["expires_at"],
            "created_at": r["created_at"],
            "active": r["active"],
            "generated": r["generated"],
            "mcp": r["mcp"],
            "profiles_id": str(r["profiles_id"]) if r["profiles_id"] else None,
        }
        for r in rows
    ]

    session_ids_str = {str(s) for s in session_ids} if session_ids else None
    profiles_ids_str = {str(p) for p in profiles_ids} if profiles_ids else None

    def matches(row: dict) -> bool:
        if session_ids_str is not None and str(row.get("session_id")) not in session_ids_str:
            return False
        if profiles_ids_str is not None and str(row.get("profiles_id")) not in profiles_ids_str:
            return False
        if active is not None and row.get("active") != active:
            return False
        return True

    merged = await hedged_search(
        redis,
        "grants",
        mv_rows=mv_dicts,
        matches_filter=matches,
        limit=limit,
        offset=offset,
        bypass_cache=bypass_cache,
    )
    return [GetGrantResponse.model_validate(r) for r in merged]
