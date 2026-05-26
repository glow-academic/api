"""Entry get — reusable data-access layer."""

from uuid import UUID

import asyncpg
from redis.asyncio import Redis

from app.tools.entries.attempt_home.types import (
    GetAttemptHomeResponse,
)
from app.utils.cache.hedged_row import hedged_search

MV_NAME = "attempt_home_mv"


async def get_attempt_home(
    conn: asyncpg.Connection,
    attempt_ids: list[UUID],
    redis: Redis,
    *,
    bypass_cache: bool = False,
) -> list[GetAttemptHomeResponse]:
    """Get attempt_home entries by attempt_id (with cache hedge).

    Composite-PK bridge: rows are keyed by ``(attempt_id, home_id)``. We
    cache by synthetic ``home_link_key`` and merge with the MV result
    filtered by ``attempt_id``.
    """
    if not attempt_ids:
        return []
    rows = await conn.fetch(
        f"SELECT * FROM {MV_NAME} WHERE attempt_id = ANY($1)", attempt_ids,
    )
    mv_dicts = [
        {
            "home_link_key": f"{r['attempt_id']}:{r['home_id']}",
            "attempt_id": str(r["attempt_id"]) if r["attempt_id"] else None,
            "home_id": str(r["home_id"]) if r["home_id"] else None,
            "session_id": str(r["session_id"]) if r.get("session_id") else None,
            "created_at": r["created_at"],
            "active": r.get("active", True),
            "generated": r.get("generated", True),
            "mcp": r.get("mcp", False),
        }
        for r in rows
    ]
    attempt_ids_str = {str(a) for a in attempt_ids}

    def matches(row: dict) -> bool:
        return str(row.get("attempt_id")) in attempt_ids_str

    merged = await hedged_search(
        redis,
        "attempt_home",
        mv_rows=mv_dicts,
        matches_filter=matches,
        limit=10000,
        offset=0,
        id_key="home_link_key",
        bypass_cache=bypass_cache,
    )
    return [GetAttemptHomeResponse.model_validate(r) for r in merged]
