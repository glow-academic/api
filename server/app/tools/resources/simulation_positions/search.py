"""Simulation Positions SEARCH — reusable data-access layer."""

from uuid import UUID

import asyncpg  # type: ignore
from redis.asyncio import Redis

from app.infra.search.search_resource import search_resource_ids
from app.tools.resources.simulation_positions.get import (
    get_simulation_positions,
)
from app.tools.resources.simulation_positions.types import (
    GetSimulationPositionResponse,
)
from app.utils.cache.cache_key import cache_key
from app.utils.cache.get_cached import get_cached
from app.utils.cache.set_cached import set_cached

JUNCTION_ARTIFACTS = ["cohort"]
DRAFT_ARTIFACTS = ["cohort"]


async def search_simulation_positions(
    conn: asyncpg.Connection,
    redis: Redis,
    limit_count: int = 20,
    offset_count: int = 0,
    exclude_ids: list[UUID] | None = None,
    simulation_ids: list[UUID] | None = None,
    bypass_cache: bool = False,
    *,
    cohort: bool = False,
) -> list[GetSimulationPositionResponse]:
    """Search simulation positions with optional artifact filters."""
    if limit_count <= 0:
        return []

    artifact_filters = {"cohort": cohort}

    extra_conditions: list[tuple[str, object]] = []
    if simulation_ids:
        extra_conditions.append(("{alias}.simulation_id = ANY(${idx})", simulation_ids))

    tags = ["resources", "simulation_positions"]
    key = cache_key(
        "/v5/resources/simulation_positions/search",
        {
            "limit_count": limit_count,
            "offset_count": offset_count,
            "exclude_ids": [str(i) for i in (exclude_ids or [])],
            "simulation_ids": sorted(str(i) for i in (simulation_ids or [])),
            **artifact_filters,
        },
    )

    if not bypass_cache:
        cached = await get_cached(key, redis=redis)
        if cached:
            return [
                GetSimulationPositionResponse.model_validate(item)
                for item in cached.get("items", [])
            ]

    ids = await search_resource_ids(
        conn,
        table="simulation_positions_resource",
        resource="simulation_positions",
        search_column=None,
        order_column="value",
        limit_count=limit_count,
        offset_count=offset_count,
        exclude_ids=exclude_ids,
        artifact_filters=artifact_filters,
        junction_artifacts=JUNCTION_ARTIFACTS,
        draft_artifacts=DRAFT_ARTIFACTS,
        extra_conditions=extra_conditions if extra_conditions else None,
    )

    if not ids:
        await set_cached(key, {"items": []}, 60, tags, redis=redis)
        return []

    items = await get_simulation_positions(conn, ids, redis, bypass_cache=True)

    await set_cached(
        key,
        {"items": [i.model_dump(mode="json") for i in items]},
        60,
        tags,
        redis=redis,
    )
    return items
