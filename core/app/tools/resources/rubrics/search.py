"""Rubrics SEARCH — reusable data-access layer."""

from uuid import UUID

import asyncpg  # type: ignore
from redis.asyncio import Redis

from app.infra.search.search_resource import search_resource_ids
from app.tools.resources.rubrics.get import get_rubrics
from app.tools.resources.rubrics.types import GetRubricResponse
from app.utils.cache.cache_key import cache_key
from app.utils.cache.get_cached import get_cached
from app.utils.cache.set_cached import set_cached

JUNCTION_ARTIFACTS = ["rubric"]


async def search_rubrics(
    conn: asyncpg.Connection,
    redis: Redis,
    search: str | None = None,
    limit_count: int = 20,
    offset_count: int = 0,
    exclude_ids: list[UUID] | None = None,
    department_ids: list[UUID] | None = None,
    simulation_rubric: bool | None = None,
    video_rubric: bool | None = None,
    standard_group_ids: list[UUID] | None = None,
    bypass_cache: bool = False,
    *,
    rubric: bool = False,
) -> list[GetRubricResponse]:
    """Search rubrics with optional artifact filters."""
    if limit_count <= 0:
        return []

    artifact_filters = {"rubric": rubric}

    extra_conditions: list[tuple[str, object]] = []
    if department_ids:
        extra_conditions.append(
            (
                "(COALESCE(array_length(${idx}::uuid[], 1), 0) = 0 OR {alias}.department_ids && ${idx}::uuid[])",
                department_ids,
            )
        )
    if simulation_rubric is not None:
        extra_conditions.append(
            ("{alias}.simulation_rubric = ${idx}::boolean", simulation_rubric)
        )
    if video_rubric is not None:
        extra_conditions.append(
            ("{alias}.video_rubric = ${idx}::boolean", video_rubric)
        )
    if standard_group_ids:
        extra_conditions.append(
            (
                "(COALESCE(array_length(${idx}::uuid[], 1), 0) = 0 OR {alias}.standard_group_ids && ${idx}::uuid[])",
                standard_group_ids,
            )
        )

    tags = ["resources", "rubrics"]
    key = cache_key(
        "/v5/resources/rubrics/search",
        {
            "search": search,
            "limit_count": limit_count,
            "offset_count": offset_count,
            "exclude_ids": [str(i) for i in (exclude_ids or [])],
            "department_ids": sorted(str(i) for i in (department_ids or [])),
            "simulation_rubric": simulation_rubric,
            "video_rubric": video_rubric,
            "standard_group_ids": sorted(str(i) for i in (standard_group_ids or [])),
            **artifact_filters,
        },
    )

    if not bypass_cache:
        cached = await get_cached(key, redis=redis)
        if cached:
            return [
                GetRubricResponse.model_validate(item)
                for item in cached.get("items", [])
            ]

    ids = await search_resource_ids(
        conn,
        table="rubrics_resource",
        resource="rubrics",
        search_column="name",
        search=search,
        limit_count=limit_count,
        offset_count=offset_count,
        exclude_ids=exclude_ids,
        artifact_filters=artifact_filters,
        junction_artifacts=JUNCTION_ARTIFACTS,
        additional_search_columns=["description"],
        extra_conditions=extra_conditions if extra_conditions else None,
    )

    if not ids:
        await set_cached(key, {"items": []}, 60, tags, redis=redis)
        return []

    items = await get_rubrics(conn, ids, redis, bypass_cache=True)

    await set_cached(
        key,
        {"items": [i.model_dump(mode="json") for i in items]},
        60,
        tags,
        redis=redis,
    )
    return items
