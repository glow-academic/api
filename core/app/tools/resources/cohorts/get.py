"""Cohorts Resource GET — reusable data-access layer."""

from uuid import UUID

import asyncpg  # type: ignore
from redis.asyncio import Redis

from app.tools.resources.cohorts.types import GetCohortResponse
from app.utils.cache.cache_key import cache_key
from app.utils.cache.get_cached import get_cached
from app.utils.cache.set_cached import set_cached


async def get_cohorts(
    conn: asyncpg.Connection,
    ids: list[UUID],
    redis: Redis,
    bypass_cache: bool = False,
) -> list[GetCohortResponse]:
    """Fetch cohorts_resource entries by IDs."""
    if not ids:
        return []

    tags = ["resources", "cohorts"]
    key = cache_key("/v5/resources/cohorts/get", {"ids": [str(id) for id in ids]})

    if not bypass_cache:
        cached = await get_cached(key, redis=redis)
        if cached:
            return [
                GetCohortResponse.model_validate(item)
                for item in cached.get("items", [])
            ]

    rows = await conn.fetch(
        """
        SELECT id, name, description, department_ids, simulation_ids, profile_ids,
               profile_persona_ids, simulation_position_ids, simulation_availability_ids,
               created_at, active, generated, mcp
        FROM cohorts_resource
        WHERE id = ANY($1)
        ORDER BY array_position($1, id)
    """,
        ids,
    )

    items = [
        GetCohortResponse(
            id=r["id"],
            name=r["name"],
            description=r["description"],
            department_ids=r["department_ids"] or [],
            simulation_ids=r["simulation_ids"] or [],
            profile_ids=r["profile_ids"] or [],
            profile_persona_ids=r["profile_persona_ids"] or [],
            simulation_position_ids=r["simulation_position_ids"] or [],
            simulation_availability_ids=r["simulation_availability_ids"] or [],
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
