"""Qualities SEARCH — reusable data-access layer."""

from uuid import UUID

import asyncpg  # type: ignore
from redis.asyncio import Redis

from app.infra.search.search_resource import search_resource_ids
from app.tools.resources.qualities.get import get_qualities
from app.tools.resources.qualities.types import GetQualityResponse
from app.utils.cache.cache_key import cache_key
from app.utils.cache.get_cached import get_cached
from app.utils.cache.set_cached import set_cached

JUNCTION_ARTIFACTS = ["model"]


async def search_qualities(
    conn: asyncpg.Connection,
    redis: Redis,
    search: str | None = None,
    limit_count: int = 20,
    offset_count: int = 0,
    exclude_ids: list[UUID] | None = None,
    bypass_cache: bool = False,
    *,
    model: bool = False,
) -> list[GetQualityResponse]:
    """Search qualities with optional artifact filters."""
    if limit_count <= 0:
        return []

    artifact_filters = {"model": model}

    tags = ["resources", "qualities"]
    key = cache_key(
        "/v5/resources/qualities/search",
        {
            "search": search,
            "limit_count": limit_count,
            "offset_count": offset_count,
            "exclude_ids": [str(i) for i in (exclude_ids or [])],
            **artifact_filters,
        },
    )

    if not bypass_cache:
        cached = await get_cached(key, redis=redis)
        if cached:
            return [
                GetQualityResponse.model_validate(item)
                for item in cached.get("items", [])
            ]

    ids = await search_resource_ids(
        conn,
        table="qualities_resource",
        resource="qualities",
        search_column="quality::text",
        search=search,
        limit_count=limit_count,
        offset_count=offset_count,
        exclude_ids=exclude_ids,
        artifact_filters=artifact_filters,
        junction_artifacts=JUNCTION_ARTIFACTS,
    )

    if not ids:
        await set_cached(key, {"items": []}, 60, tags, redis=redis)
        return []

    items = await get_qualities(conn, ids, redis, bypass_cache=True)

    await set_cached(
        key,
        {"items": [i.model_dump(mode="json") for i in items]},
        60,
        tags,
        redis=redis,
    )
    return items
