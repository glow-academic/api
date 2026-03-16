"""Scenarios SEARCH — reusable data-access layer."""

from uuid import UUID

import asyncpg  # type: ignore
from redis.asyncio import Redis

from app.infra.search.search_resource import search_resource_ids
from app.tools.resources.scenarios.get import get_scenarios
from app.tools.resources.scenarios.types import GetScenarioResponse
from app.utils.cache.cache_key import cache_key
from app.utils.cache.get_cached import get_cached
from app.utils.cache.set_cached import set_cached

JUNCTION_ARTIFACTS = ["scenario", "simulation"]


async def search_scenarios(
    conn: asyncpg.Connection,
    redis: Redis,
    search: str | None = None,
    limit_count: int = 20,
    offset_count: int = 0,
    department_ids: list[UUID] | None = None,
    suggest_source: str | None = None,
    exclude_ids: list[UUID] | None = None,
    persona_ids: list[UUID] | None = None,
    parameter_ids: list[UUID] | None = None,
    problem_statement_enabled: bool | None = None,
    objectives_enabled: bool | None = None,
    video_enabled: bool | None = None,
    images_enabled: bool | None = None,
    questions_enabled: bool | None = None,
    bypass_cache: bool = False,
    *,
    scenario: bool = False,
    simulation: bool = False,
) -> list[GetScenarioResponse]:
    """Search scenarios with optional artifact filters."""
    if limit_count <= 0:
        return []

    artifact_filters = {"scenario": scenario, "simulation": simulation}

    extra_conditions: list[tuple[str, object]] = []
    if department_ids:
        extra_conditions.append(
            (
                "({alias}.department_ids IS NULL OR array_length({alias}.department_ids, 1) IS NULL OR {alias}.department_ids && ${idx}::uuid[])",
                department_ids,
            )
        )
    if persona_ids:
        extra_conditions.append(
            (
                "(COALESCE(array_length(${idx}::uuid[], 1), 0) = 0 OR {alias}.persona_ids && ${idx}::uuid[])",
                persona_ids,
            )
        )
    if parameter_ids:
        extra_conditions.append(
            (
                "(COALESCE(array_length(${idx}::uuid[], 1), 0) = 0 OR {alias}.parameter_field_ids && ${idx}::uuid[])",
                parameter_ids,
            )
        )
    if problem_statement_enabled is not None:
        extra_conditions.append(
            (
                "{alias}.problem_statement_enabled = ${idx}::boolean",
                problem_statement_enabled,
            )
        )
    if objectives_enabled is not None:
        extra_conditions.append(
            ("{alias}.objectives_enabled = ${idx}::boolean", objectives_enabled)
        )
    if video_enabled is not None:
        extra_conditions.append(
            ("{alias}.video_enabled = ${idx}::boolean", video_enabled)
        )
    if images_enabled is not None:
        extra_conditions.append(
            ("{alias}.images_enabled = ${idx}::boolean", images_enabled)
        )
    if questions_enabled is not None:
        extra_conditions.append(
            ("{alias}.questions_enabled = ${idx}::boolean", questions_enabled)
        )

    tags = ["resources", "scenarios"]
    key = cache_key(
        "/v5/resources/scenarios/search",
        {
            "search": search,
            "limit_count": limit_count,
            "offset_count": offset_count,
            "department_ids": [str(i) for i in department_ids]
            if department_ids
            else None,
            "suggest_source": suggest_source,
            "exclude_ids": [str(i) for i in exclude_ids] if exclude_ids else None,
            "persona_ids": sorted(str(i) for i in (persona_ids or [])),
            "parameter_ids": sorted(str(i) for i in (parameter_ids or [])),
            "problem_statement_enabled": problem_statement_enabled,
            "objectives_enabled": objectives_enabled,
            "video_enabled": video_enabled,
            "images_enabled": images_enabled,
            "questions_enabled": questions_enabled,
            **artifact_filters,
        },
    )

    if not bypass_cache:
        cached = await get_cached(key, redis=redis)
        if cached:
            return [
                GetScenarioResponse.model_validate(item)
                for item in cached.get("items", [])
            ]

    ids = await search_resource_ids(
        conn,
        table="scenarios_resource",
        resource="scenarios",
        search_column="name",
        additional_search_columns=["description"],
        search=search,
        limit_count=limit_count,
        offset_count=offset_count,
        exclude_ids=exclude_ids,
        artifact_filters=artifact_filters,
        junction_artifacts=JUNCTION_ARTIFACTS,
        extra_conditions=extra_conditions if extra_conditions else None,
    )

    if not ids:
        await set_cached(key, {"items": []}, 60, tags, redis=redis)
        return []

    items = await get_scenarios(conn, ids, redis, bypass_cache=True)

    await set_cached(
        key,
        {"items": [i.model_dump(mode="json") for i in items]},
        60,
        tags,
        redis=redis,
    )
    return items
