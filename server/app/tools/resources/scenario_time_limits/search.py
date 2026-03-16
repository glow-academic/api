"""Scenario Time Limits SEARCH — reusable data-access layer."""

from uuid import UUID

import asyncpg  # type: ignore
from redis.asyncio import Redis

from app.infra.search.search_resource import search_resource_ids
from app.tools.resources.scenario_time_limits.get import (
    get_scenario_time_limits,
)
from app.tools.resources.scenario_time_limits.types import (
    GetScenarioTimeLimitResponse,
)
from app.utils.cache.cache_key import cache_key
from app.utils.cache.get_cached import get_cached
from app.utils.cache.set_cached import set_cached

JUNCTION_ARTIFACTS = ["simulation"]
DRAFT_ARTIFACTS = ["simulation"]


async def search_scenario_time_limits(
    conn: asyncpg.Connection,
    redis: Redis,
    search: str | None = None,
    limit_count: int = 20,
    offset_count: int = 0,
    exclude_ids: list[UUID] | None = None,
    scenario_ids: list[UUID] | None = None,
    negative: bool | None = None,
    bypass_cache: bool = False,
    *,
    simulation: bool = False,
) -> list[GetScenarioTimeLimitResponse]:
    """Search scenario time limits with optional artifact filters."""
    if limit_count <= 0:
        return []

    artifact_filters = {
        "simulation": simulation,
    }

    extra_conditions: list[tuple[str, object]] = [
        ("{alias}.active = ${idx}::boolean", True),
    ]

    if scenario_ids:
        extra_conditions.append(("{alias}.scenario_id = ANY(${idx})", scenario_ids))

    if negative is not None:
        extra_conditions.append(("{alias}.negative = ${idx}::boolean", negative))

    tags = ["resources", "scenario_time_limits"]
    key = cache_key(
        "/v5/resources/scenario_time_limits/search",
        {
            "search": search,
            "limit_count": limit_count,
            "offset_count": offset_count,
            "exclude_ids": [str(i) for i in (exclude_ids or [])],
            "scenario_ids": [str(i) for i in (scenario_ids or [])],
            "negative": negative,
            **artifact_filters,
        },
    )

    if not bypass_cache:
        cached = await get_cached(key, redis=redis)
        if cached:
            return [
                GetScenarioTimeLimitResponse.model_validate(item)
                for item in cached.get("items", [])
            ]

    ids = await search_resource_ids(
        conn,
        table="scenario_time_limits_resource",
        resource="scenario_time_limits",
        search_column=None,
        search=None,
        limit_count=limit_count,
        offset_count=offset_count,
        exclude_ids=exclude_ids,
        artifact_filters=artifact_filters,
        junction_artifacts=JUNCTION_ARTIFACTS,
        draft_artifacts=DRAFT_ARTIFACTS,
        order_column="time_limit_seconds",
        extra_conditions=extra_conditions,
    )

    if not ids:
        await set_cached(key, {"items": []}, 60, tags, redis=redis)
        return []

    items = await get_scenario_time_limits(conn, ids, redis, bypass_cache=True)

    await set_cached(
        key,
        {"items": [i.model_dump(mode="json") for i in items]},
        60,
        tags,
        redis=redis,
    )
    return items
