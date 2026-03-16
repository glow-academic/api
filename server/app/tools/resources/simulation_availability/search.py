"""Simulation Availability SEARCH — reusable data-access layer."""

from uuid import UUID

import asyncpg  # type: ignore
from redis.asyncio import Redis

from app.infra.search.search_resource import search_resource_ids
from app.tools.resources.simulation_availability.get import (
    get_simulation_availability,
)
from app.tools.resources.simulation_availability.types import (
    GetSimulationAvailabilityResponse,
)
from app.utils.cache.cache_key import cache_key
from app.utils.cache.get_cached import get_cached
from app.utils.cache.set_cached import set_cached

JUNCTION_ARTIFACTS = ["cohort"]
DRAFT_ARTIFACTS = ["cohort"]


async def search_simulation_availability(
    conn: asyncpg.Connection,
    redis: Redis,
    search: str | None = None,
    limit_count: int = 20,
    offset_count: int = 0,
    exclude_ids: list[UUID] | None = None,
    simulation_ids: list[UUID] | None = None,
    availability_type: str | None = None,
    bypass_cache: bool = False,
    *,
    cohort: bool = False,
) -> list[GetSimulationAvailabilityResponse]:
    """Search simulation availability with optional artifact filters."""
    if limit_count <= 0:
        return []

    artifact_filters = {
        "cohort": cohort,
    }

    extra_conditions: list[tuple[str, object]] = [
        ("{alias}.active = ${idx}::boolean", True),
    ]

    if simulation_ids:
        extra_conditions.append(("{alias}.simulation_id = ANY(${idx})", simulation_ids))

    if availability_type is not None:
        extra_conditions.append(
            ("{alias}.type = ${idx}::availability_type", availability_type)
        )

    tags = ["resources", "simulation_availability"]
    key = cache_key(
        "/v5/resources/simulation_availability/search",
        {
            "search": search,
            "limit_count": limit_count,
            "offset_count": offset_count,
            "exclude_ids": [str(i) for i in (exclude_ids or [])],
            "simulation_ids": [str(i) for i in (simulation_ids or [])],
            "availability_type": availability_type,
            **artifact_filters,
        },
    )

    if not bypass_cache:
        cached = await get_cached(key, redis=redis)
        if cached:
            return [
                GetSimulationAvailabilityResponse.model_validate(item)
                for item in cached.get("items", [])
            ]

    ids = await search_resource_ids(
        conn,
        table="simulation_availability_resource",
        resource="simulation_availability",
        search_column=None,
        search=None,
        limit_count=limit_count,
        offset_count=offset_count,
        exclude_ids=exclude_ids,
        artifact_filters=artifact_filters,
        junction_artifacts=JUNCTION_ARTIFACTS,
        draft_artifacts=DRAFT_ARTIFACTS,
        order_column="time",
        extra_conditions=extra_conditions,
    )

    if not ids:
        await set_cached(key, {"items": []}, 60, tags, redis=redis)
        return []

    items = await get_simulation_availability(conn, ids, redis, bypass_cache=True)

    await set_cached(
        key,
        {"items": [i.model_dump(mode="json") for i in items]},
        60,
        tags,
        redis=redis,
    )
    return items
