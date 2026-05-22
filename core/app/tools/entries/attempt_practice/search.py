"""Attempt practice search — filtered/paginated query against attempt_practice_mv."""

from uuid import UUID

import asyncpg  # type: ignore
from redis.asyncio import Redis

from app.infra.docs.resolve_mv_source import resolve_mv_source
from app.tools.entries.attempt_practice.types import (
    GetAttemptPracticeResponse,
)
from app.utils.cache.hedged_row import hedged_search

MV_NAME = "attempt_practice_mv"


async def search_attempt_practice_entries(
    conn: asyncpg.Connection,
    redis: Redis,
    attempt_ids: list[UUID] | None = None,
    practice_ids: list[UUID] | None = None,
    limit: int = 20,
    offset: int = 0,
    bypass_mv: bool = False,
    bypass_cache: bool = False,
) -> list[GetAttemptPracticeResponse]:
    """Search attempt_practice entries from attempt_practice_mv with declarative filters."""
    source = await resolve_mv_source(conn, MV_NAME, bypass_mv)

    rows = await conn.fetch(
        f"""
        SELECT attempt_id, practice_id, created_at, active, generated, mcp, session_id
        FROM {source}
        WHERE ($1::uuid[] IS NULL OR attempt_id = ANY($1))
          AND ($2::uuid[] IS NULL OR practice_id = ANY($2))
        ORDER BY created_at DESC
        LIMIT $3 OFFSET $4
        """,
        attempt_ids,
        practice_ids,
        limit + offset + 1000,
        0,
    )

    mv_dicts = [
        {
            "id": f"{r['attempt_id']}:{r['practice_id']}",
            "attempt_id": str(r["attempt_id"]),
            "practice_id": str(r["practice_id"]),
            "created_at": r["created_at"],
            "active": r["active"],
            "generated": r["generated"],
            "mcp": r["mcp"],
            "session_id": str(r["session_id"]) if r["session_id"] else None,
        }
        for r in rows
    ]

    attempt_ids_str = {str(a) for a in attempt_ids} if attempt_ids else None
    practice_ids_str = {str(p) for p in practice_ids} if practice_ids else None

    def matches(row: dict) -> bool:
        if attempt_ids_str is not None and str(row.get("attempt_id")) not in attempt_ids_str:
            return False
        if practice_ids_str is not None and str(row.get("practice_id")) not in practice_ids_str:
            return False
        # MV filters active=true; mirror that.
        if not row.get("active", True):
            return False
        return True

    merged = await hedged_search(
        redis,
        "attempt_practice",
        mv_rows=mv_dicts,
        matches_filter=matches,
        limit=limit,
        offset=offset,
        bypass_cache=bypass_cache,
    )
    # Strip synthetic 'id' before validating; response model doesn't expect it.
    return [
        GetAttemptPracticeResponse.model_validate({k: v for k, v in r.items() if k != "id"})
        for r in merged
    ]
