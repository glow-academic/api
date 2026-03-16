"""Model Rubrics SEARCH — reusable data-access layer."""

from uuid import UUID

import asyncpg  # type: ignore
from redis.asyncio import Redis

from app.infra.search.search_resource import search_resource_ids
from app.tools.resources.model_rubrics.get import get_model_rubrics
from app.tools.resources.model_rubrics.types import GetModelRubricResponse
from app.utils.cache.cache_key import cache_key
from app.utils.cache.get_cached import get_cached
from app.utils.cache.set_cached import set_cached

JUNCTION_ARTIFACTS = ["eval"]


async def search_model_rubrics(
    conn: asyncpg.Connection,
    redis: Redis,
    limit_count: int = 20,
    offset_count: int = 0,
    exclude_ids: list[UUID] | None = None,
    model_ids: list[UUID] | None = None,
    rubric_ids: list[UUID] | None = None,
    bypass_cache: bool = False,
    *,
    eval: bool = False,
) -> list[GetModelRubricResponse]:
    """Search model rubrics with optional artifact filters."""
    if limit_count <= 0:
        return []

    artifact_filters = {"eval": eval}

    extra_conditions: list[tuple[str, object]] = []

    if model_ids:
        extra_conditions.append(("{alias}.model_id = ANY(${idx})", model_ids))
    if rubric_ids:
        extra_conditions.append(("{alias}.rubric_id = ANY(${idx})", rubric_ids))

    tags = ["resources", "model_rubrics"]
    key = cache_key(
        "/v5/resources/model_rubrics/search",
        {
            "limit_count": limit_count,
            "offset_count": offset_count,
            "exclude_ids": [str(i) for i in (exclude_ids or [])],
            "model_ids": sorted(str(i) for i in (model_ids or [])),
            "rubric_ids": sorted(str(i) for i in (rubric_ids or [])),
            **artifact_filters,
        },
    )

    if not bypass_cache:
        cached = await get_cached(key, redis=redis)
        if cached:
            return [
                GetModelRubricResponse.model_validate(item)
                for item in cached.get("items", [])
            ]

    ids = await search_resource_ids(
        conn,
        table="model_rubrics_resource",
        resource="model_rubrics",
        search_column=None,
        order_column="created_at",
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

    items = await get_model_rubrics(conn, ids, redis, bypass_cache=True)

    await set_cached(
        key,
        {"items": [i.model_dump(mode="json") for i in items]},
        60,
        tags,
        redis=redis,
    )
    return items
