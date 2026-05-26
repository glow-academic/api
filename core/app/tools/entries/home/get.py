"""home/get — reusable data-access layer."""

from uuid import UUID

import asyncpg  # type: ignore
from redis.asyncio import Redis

from app.tools.entries.home.types import GetHomeResponse
from app.utils.cache.hedged_row import read_back_row

MV_NAME = "home_mv"


async def get_homes(
    conn: asyncpg.Connection,
    ids: list[UUID],
    redis: Redis,
    *,
    bypass_cache: bool = False,
) -> list[GetHomeResponse]:
    """Get home entries by IDs from home_mv."""
    if not ids:
        return []

    cached_results: dict[str, GetHomeResponse] = {}
    missing_ids: list[UUID] = []
    if not bypass_cache:
        for hid in ids:
            cached = await read_back_row(redis, "home", hid)
            if cached is not None:
                cached_results[str(hid)] = GetHomeResponse.model_validate(cached)
            else:
                missing_ids.append(hid)
    else:
        missing_ids = list(ids)

    mv_results: dict[str, GetHomeResponse] = {}
    if missing_ids:
        rows = await conn.fetch(
            f"""
            SELECT home_id, simulation_ids, cohort_ids, department_ids,
                   profile_ids, chat_ids, scenario_ids, created_at, updated_at, active
            FROM {MV_NAME}
            WHERE home_id = ANY($1)
            """,
            missing_ids,
        )
        for r in rows:
            mv_results[str(r["home_id"])] = GetHomeResponse(
                id=r["home_id"],
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

    out: list[GetHomeResponse] = []
    for hid in ids:
        key = str(hid)
        if key in cached_results:
            out.append(cached_results[key])
        elif key in mv_results:
            out.append(mv_results[key])
    return out
