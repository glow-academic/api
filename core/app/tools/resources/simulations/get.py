"""Simulations Resource GET — reusable data-access layer."""

from uuid import UUID

import asyncpg  # type: ignore
from redis.asyncio import Redis

from app.tools.resources.simulations.types import GetSimulationResponse
from app.utils.cache.cache_key import cache_key
from app.utils.cache.get_cached import get_cached
from app.utils.cache.set_cached import set_cached


async def get_simulations(
    conn: asyncpg.Connection,
    ids: list[UUID],
    redis: Redis,
    bypass_cache: bool = False,
) -> list[GetSimulationResponse]:
    """Fetch simulations_resource entries by IDs."""
    if not ids:
        return []

    tags = ["resources", "simulations"]
    key = cache_key(
        "/v5/resources/simulations/get", {"ids": [str(id) for id in ids]}
    )

    if not bypass_cache:
        cached = await get_cached(key, redis=redis)
        if cached:
            return [
                GetSimulationResponse.model_validate(item)
                for item in cached.get("items", [])
            ]

    rows = await conn.fetch(
        """
        SELECT id, name, description, department_ids, scenario_ids, scenario_rubric_ids,
               scenario_time_limit_ids, scenario_position_ids, scenario_flag_ids,
               practice, created_at, active, generated, mcp
        FROM simulations_resource
        WHERE id = ANY($1)
        ORDER BY array_position($1, id)
    """,
        ids,
    )

    items = [
        GetSimulationResponse(
            id=r["id"],
            name=r["name"],
            description=r["description"],
            department_ids=r["department_ids"] or [],
            scenario_ids=r["scenario_ids"] or [],
            scenario_rubric_ids=r["scenario_rubric_ids"] or [],
            scenario_time_limit_ids=r["scenario_time_limit_ids"] or [],
            scenario_position_ids=r["scenario_position_ids"] or [],
            scenario_flag_ids=r["scenario_flag_ids"] or [],
            practice=r["practice"],
            created_at=r["created_at"],
            active=r["active"],
            generated=r["generated"],
            mcp=r["mcp"],
        )
        for r in rows
    ]

    if not bypass_cache:
        await set_cached(
            key,
            {"items": [i.model_dump(mode="json") for i in items]},
            60,
            tags,
            redis=redis,
        )
    return items
