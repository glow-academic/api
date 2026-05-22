"""Home search — filtered/paginated query against home_mv."""

import asyncpg  # type: ignore
from redis.asyncio import Redis

from app.infra.docs.resolve_mv_source import resolve_mv_source
from app.tools.entries.home.types import GetHomeResponse
from app.utils.cache.hedged_row import hedged_search

MV_NAME = "home_mv"


async def search_homes(
    conn: asyncpg.Connection,
    redis: Redis,
    limit: int = 20,
    offset: int = 0,
    bypass_mv: bool = False,
    bypass_cache: bool = False,
) -> list[GetHomeResponse]:
    """Search home entries from home_mv with declarative filters."""
    source = await resolve_mv_source(conn, MV_NAME, bypass_mv)

    rows = await conn.fetch(
        f"""
        SELECT home_id, simulation_ids, cohort_ids, department_ids,
               profile_ids, chat_ids, scenario_ids, created_at, updated_at, active
        FROM {source}
        ORDER BY created_at DESC
        LIMIT $1 OFFSET $2
        """,
        limit + offset + 1000,
        0,
    )

    mv_dicts = [
        {
            "id": str(r["home_id"]),
            "simulation_ids": [str(x) for x in r["simulation_ids"]],
            "cohort_ids": [str(x) for x in r["cohort_ids"]],
            "department_ids": [str(x) for x in r["department_ids"]],
            "profile_ids": [str(x) for x in r["profile_ids"]],
            "chat_ids": [str(x) for x in r["chat_ids"]],
            "scenario_ids": [str(x) for x in r["scenario_ids"]],
            "created_at": r["created_at"],
            "updated_at": r["updated_at"],
            "active": r["active"],
        }
        for r in rows
    ]

    def matches(row: dict) -> bool:
        return True

    merged = await hedged_search(
        redis,
        "home",
        mv_rows=mv_dicts,
        matches_filter=matches,
        limit=limit,
        offset=offset,
        bypass_cache=bypass_cache,
    )
    return [GetHomeResponse.model_validate(r) for r in merged]
