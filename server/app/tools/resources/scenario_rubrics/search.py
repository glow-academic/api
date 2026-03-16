"""Scenario Rubrics SEARCH — reusable data-access layer."""

from uuid import UUID

import asyncpg  # type: ignore
from redis.asyncio import Redis

from app.infra.search.search_resource import search_resource_ids
from app.tools.resources.scenario_rubrics.get import get_scenario_rubrics
from app.tools.resources.scenario_rubrics.types import (
    GetScenarioRubricResponse,
)
from app.utils.cache.cache_key import cache_key
from app.utils.cache.get_cached import get_cached
from app.utils.cache.set_cached import set_cached

JUNCTION_ARTIFACTS = ["simulation"]

DRAFT_ARTIFACTS = ["simulation"]


async def search_scenario_rubrics(
    conn: asyncpg.Connection,
    redis: Redis,
    limit_count: int = 20,
    offset_count: int = 0,
    exclude_ids: list[UUID] | None = None,
    scenario_ids: list[UUID] | None = None,
    rubric_ids: list[UUID] | None = None,
    bypass_cache: bool = False,
    *,
    simulation: bool = False,
) -> list[GetScenarioRubricResponse]:
    """Search scenario rubrics with optional artifact filters."""
    if limit_count <= 0:
        return []

    artifact_filters = {"simulation": simulation}

    extra_conditions: list[tuple[str, object]] = []

    if scenario_ids:
        extra_conditions.append(("{alias}.scenario_id = ANY(${idx})", scenario_ids))
    if rubric_ids:
        extra_conditions.append(("{alias}.rubric_id = ANY(${idx})", rubric_ids))

    tags = ["resources", "scenario_rubrics"]
    key = cache_key(
        "/v5/resources/scenario_rubrics/search",
        {
            "limit_count": limit_count,
            "offset_count": offset_count,
            "exclude_ids": [str(i) for i in (exclude_ids or [])],
            "scenario_ids": sorted(str(i) for i in (scenario_ids or [])),
            "rubric_ids": sorted(str(i) for i in (rubric_ids or [])),
            **artifact_filters,
        },
    )

    if not bypass_cache:
        cached = await get_cached(key, redis=redis)
        if cached:
            return [
                GetScenarioRubricResponse.model_validate(item)
                for item in cached.get("items", [])
            ]

    ids = await search_resource_ids(
        conn,
        table="scenario_rubrics_resource",
        resource="scenario_rubrics",
        search_column=None,
        order_column="created_at",
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

    items = await get_scenario_rubrics(conn, ids, redis, bypass_cache=True)

    await set_cached(
        key,
        {"items": [i.model_dump(mode="json") for i in items]},
        60,
        tags,
        redis=redis,
    )
    return items
