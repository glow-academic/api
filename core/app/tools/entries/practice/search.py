"""Practice search — filtered/paginated query against practice_mv."""

from uuid import UUID

import asyncpg  # type: ignore
from redis.asyncio import Redis

from app.infra.docs.resolve_mv_source import resolve_mv_source
from app.tools.entries.practice.types import GetPracticeResponse
from app.utils.cache.hedged_row import hedged_search

MV_NAME = "practice_mv"


async def search_practices(
    conn: asyncpg.Connection,
    redis: Redis,
    session_ids: list[UUID] | None = None,
    limit: int = 20,
    offset: int = 0,
    bypass_mv: bool = False,
    bypass_cache: bool = False,
) -> list[GetPracticeResponse]:
    """Search practice entries from practice_mv with declarative filters."""
    source = await resolve_mv_source(conn, MV_NAME, bypass_mv)

    rows = await conn.fetch(
        f"""
        SELECT practice_id, session_id, simulation_ids, cohort_ids, department_ids,
               profile_ids, chat_ids, scenario_ids,
               created_at, updated_at, active
        FROM {source}
        WHERE ($1::uuid[] IS NULL OR session_id = ANY($1))
        ORDER BY created_at DESC
        LIMIT $2 OFFSET $3
        """,
        session_ids,
        limit + offset + 1000,
        0,
    )

    mv_dicts = [
        {
            "id": str(r["practice_id"]),
            "session_id": str(r["session_id"]) if r["session_id"] else None,
            "simulation_ids": [str(x) for x in (r["simulation_ids"] or [])],
            "cohort_ids": [str(x) for x in (r["cohort_ids"] or [])],
            "department_ids": [str(x) for x in (r["department_ids"] or [])],
            "profile_ids": [str(x) for x in (r["profile_ids"] or [])],
            "chat_ids": [str(x) for x in (r["chat_ids"] or [])],
            "scenario_ids": [str(x) for x in (r["scenario_ids"] or [])],
            "created_at": r["created_at"],
            "updated_at": r["updated_at"],
            "active": r["active"],
        }
        for r in rows
    ]

    session_ids_str = {str(s) for s in session_ids} if session_ids else None

    def matches(row: dict) -> bool:
        if session_ids_str is not None and str(row.get("session_id")) not in session_ids_str:
            return False
        return True

    merged = await hedged_search(
        redis,
        "practice",
        mv_rows=mv_dicts,
        matches_filter=matches,
        limit=limit,
        offset=offset,
        bypass_cache=bypass_cache,
    )
    return [
        GetPracticeResponse(
            id=r["id"],
            simulation_ids=r["simulation_ids"],
            cohort_ids=r["cohort_ids"],
            department_ids=r["department_ids"],
            profile_ids=r["profile_ids"],
            chat_ids=r["chat_ids"],
            scenario_ids=r["scenario_ids"],
            created_at=r["created_at"],
            updated_at=r["updated_at"],
            active=r["active"],
        )
        for r in merged
    ]
