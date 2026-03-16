"""Modalities SEARCH — reusable data-access layer."""

from uuid import UUID

import asyncpg  # type: ignore
from redis.asyncio import Redis

from app.infra.search.search_resource import search_resource_ids
from app.tools.resources.modalities.get import get_modalities
from app.tools.resources.modalities.types import GetModalityResponse
from app.utils.cache.cache_key import cache_key
from app.utils.cache.get_cached import get_cached
from app.utils.cache.set_cached import set_cached

JUNCTION_ARTIFACTS = ["model"]


async def search_modalities(
    conn: asyncpg.Connection,
    redis: Redis,
    search: str | None = None,
    limit_count: int = 20,
    offset_count: int = 0,
    exclude_ids: list[UUID] | None = None,
    modality: str | None = None,
    is_input: bool | None = None,
    bypass_cache: bool = False,
    *,
    model: bool = False,
) -> list[GetModalityResponse]:
    """Search modalities with optional artifact filters."""
    if limit_count <= 0:
        return []

    artifact_filters = {"model": model}

    extra_conditions: list[tuple[str, object]] = []
    if modality is not None:
        extra_conditions.append(("{alias}.modality::text = ${idx}", modality))
    if is_input is not None:
        extra_conditions.append(("{alias}.is_input = ${idx}::boolean", is_input))

    tags = ["resources", "modalities"]
    key = cache_key(
        "/v5/resources/modalities/search",
        {
            "search": search,
            "limit_count": limit_count,
            "offset_count": offset_count,
            "exclude_ids": [str(i) for i in (exclude_ids or [])],
            "modality": modality,
            "is_input": is_input,
            **artifact_filters,
        },
    )

    if not bypass_cache:
        cached = await get_cached(key, redis=redis)
        if cached:
            return [
                GetModalityResponse.model_validate(item)
                for item in cached.get("items", [])
            ]

    ids = await search_resource_ids(
        conn,
        table="modalities_resource",
        resource="modalities",
        search_column="modality::text",
        search=search,
        limit_count=limit_count,
        offset_count=offset_count,
        exclude_ids=exclude_ids,
        artifact_filters=artifact_filters,
        junction_artifacts=JUNCTION_ARTIFACTS,
        order_column="modality",
        extra_conditions=extra_conditions if extra_conditions else None,
    )

    if not ids:
        await set_cached(key, {"items": []}, 60, tags, redis=redis)
        return []

    items = await get_modalities(conn, ids, redis, bypass_cache=True)

    await set_cached(
        key,
        {"items": [i.model_dump(mode="json") for i in items]},
        60,
        tags,
        redis=redis,
    )
    return items
