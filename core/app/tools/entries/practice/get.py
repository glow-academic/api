"""practice/get — reusable data-access layer."""

from uuid import UUID

import asyncpg  # type: ignore
from redis.asyncio import Redis

from app.tools.entries.practice.types import GetPracticeResponse
from app.utils.cache.hedged_row import read_back_row

MV_NAME = "practice_mv"


async def get_practices(
    conn: asyncpg.Connection,
    ids: list[UUID],
    redis: Redis,
    *,
    bypass_cache: bool = False,
) -> list[GetPracticeResponse]:
    """Get practice entries by IDs from practice_mv."""
    if not ids:
        return []

    cached_results: dict[str, GetPracticeResponse] = {}
    missing_ids: list[UUID] = []
    if not bypass_cache:
        for pid in ids:
            cached = await read_back_row(redis, "practice", pid)
            if cached is not None:
                cached_results[str(pid)] = GetPracticeResponse.model_validate(cached)
            else:
                missing_ids.append(pid)
    else:
        missing_ids = list(ids)

    mv_results: dict[str, GetPracticeResponse] = {}
    if missing_ids:
        rows = await conn.fetch(
            f"""
            SELECT practice_id, simulation_ids, cohort_ids, department_ids,
                   profile_ids, chat_ids, scenario_ids,
                   created_at, updated_at, active
            FROM {MV_NAME}
            WHERE practice_id = ANY($1)
            """,
            missing_ids,
        )
        for r in rows:
            mv_results[str(r["practice_id"])] = GetPracticeResponse(
                id=r["practice_id"],
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

    out: list[GetPracticeResponse] = []
    for pid in ids:
        key = str(pid)
        if key in cached_results:
            out.append(cached_results[key])
        elif key in mv_results:
            out.append(mv_results[key])
    return out
