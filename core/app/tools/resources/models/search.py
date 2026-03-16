"""Models SEARCH — reusable data-access layer."""

from uuid import UUID

import asyncpg  # type: ignore
from redis.asyncio import Redis

from app.infra.search.search_resource import search_resource_ids
from app.tools.resources.models.get import get_models
from app.tools.resources.models.types import GetModelResponse
from app.utils.cache.cache_key import cache_key
from app.utils.cache.get_cached import get_cached
from app.utils.cache.set_cached import set_cached

JUNCTION_ARTIFACTS = ["agent", "model"]


async def search_models(
    conn: asyncpg.Connection,
    redis: Redis,
    search: str | None = None,
    limit_count: int = 20,
    offset_count: int = 0,
    exclude_ids: list[UUID] | None = None,
    department_ids: list[UUID] | None = None,
    provider_ids: list[UUID] | None = None,
    temperature_level_ids: list[UUID] | None = None,
    reasoning_level_ids: list[UUID] | None = None,
    quality_ids: list[UUID] | None = None,
    voice_ids: list[UUID] | None = None,
    modality_ids: list[UUID] | None = None,
    bypass_cache: bool = False,
    *,
    agent: bool = False,
    model: bool = False,
) -> list[GetModelResponse]:
    """Search models with optional artifact filters."""
    if limit_count <= 0:
        return []

    artifact_filters = {"agent": agent, "model": model}

    extra_conditions: list[tuple[str, object]] = []
    if department_ids:
        extra_conditions.append(
            (
                "(COALESCE(array_length(${idx}::uuid[], 1), 0) = 0 OR {alias}.department_ids && ${idx}::uuid[])",
                department_ids,
            )
        )
    if provider_ids:
        extra_conditions.append(
            (
                "(COALESCE(array_length(${idx}::uuid[], 1), 0) = 0 OR {alias}.provider_id = ANY(${idx}))",
                provider_ids,
            )
        )
    if temperature_level_ids:
        extra_conditions.append(
            (
                "(COALESCE(array_length(${idx}::uuid[], 1), 0) = 0 OR {alias}.temperature_level_ids && ${idx}::uuid[])",
                temperature_level_ids,
            )
        )
    if reasoning_level_ids:
        extra_conditions.append(
            (
                "(COALESCE(array_length(${idx}::uuid[], 1), 0) = 0 OR {alias}.reasoning_level_ids && ${idx}::uuid[])",
                reasoning_level_ids,
            )
        )
    if quality_ids:
        extra_conditions.append(
            (
                "(COALESCE(array_length(${idx}::uuid[], 1), 0) = 0 OR {alias}.quality_ids && ${idx}::uuid[])",
                quality_ids,
            )
        )
    if voice_ids:
        extra_conditions.append(
            (
                "(COALESCE(array_length(${idx}::uuid[], 1), 0) = 0 OR {alias}.voice_ids && ${idx}::uuid[])",
                voice_ids,
            )
        )
    if modality_ids:
        extra_conditions.append(
            (
                "(COALESCE(array_length(${idx}::uuid[], 1), 0) = 0 OR {alias}.modality_ids && ${idx}::uuid[])",
                modality_ids,
            )
        )

    tags = ["resources", "models"]
    key = cache_key(
        "/v5/resources/models/search",
        {
            "search": search,
            "limit_count": limit_count,
            "offset_count": offset_count,
            "exclude_ids": [str(i) for i in (exclude_ids or [])],
            "department_ids": sorted(str(i) for i in (department_ids or [])),
            "provider_ids": sorted(str(i) for i in (provider_ids or [])),
            "temperature_level_ids": sorted(
                str(i) for i in (temperature_level_ids or [])
            ),
            "reasoning_level_ids": sorted(str(i) for i in (reasoning_level_ids or [])),
            "quality_ids": sorted(str(i) for i in (quality_ids or [])),
            "voice_ids": sorted(str(i) for i in (voice_ids or [])),
            "modality_ids": sorted(str(i) for i in (modality_ids or [])),
            **artifact_filters,
        },
    )

    if not bypass_cache:
        cached = await get_cached(key, redis=redis)
        if cached:
            return [
                GetModelResponse.model_validate(item)
                for item in cached.get("items", [])
            ]

    ids = await search_resource_ids(
        conn,
        table="models_resource",
        resource="models",
        search_column="name",
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

    items = await get_models(conn, ids, redis, bypass_cache=True)

    await set_cached(
        key,
        {"items": [i.model_dump(mode="json") for i in items]},
        60,
        tags,
        redis=redis,
    )
    return items
