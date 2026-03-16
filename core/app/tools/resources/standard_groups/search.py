"""Standard Groups SEARCH — reusable data-access layer."""

from uuid import UUID

import asyncpg  # type: ignore
from redis.asyncio import Redis

from app.infra.search.search_resource import search_resource_ids
from app.tools.resources.standard_groups.get import get_standard_groups
from app.tools.resources.standard_groups.types import GetStandardGroupResponse
from app.utils.cache.cache_key import cache_key
from app.utils.cache.get_cached import get_cached
from app.utils.cache.set_cached import set_cached

JUNCTION_ARTIFACTS = ["rubric"]


async def search_standard_groups(
    conn: asyncpg.Connection,
    redis: Redis,
    search: str | None = None,
    limit_count: int = 20,
    offset_count: int = 0,
    exclude_ids: list[UUID] | None = None,
    bypass_cache: bool = False,
    *,
    rubric: bool = False,
) -> list[GetStandardGroupResponse]:
    """Search standard_groups with optional artifact filters."""
    if limit_count <= 0:
        return []

    artifact_filters = {"rubric": rubric}

    tags = ["resources", "standard_groups"]
    key = cache_key(
        "/v5/resources/standard_groups/search",
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
                GetStandardGroupResponse.model_validate(item)
                for item in cached.get("items", [])
            ]

    ids = await search_resource_ids(
        conn,
        table="standard_groups_resource",
        resource="standard_groups",
        search_column="name",
        search=search,
        limit_count=limit_count,
        offset_count=offset_count,
        exclude_ids=exclude_ids,
        artifact_filters=artifact_filters,
        junction_artifacts=JUNCTION_ARTIFACTS,
        additional_search_columns=["description"],
    )

    if not ids:
        await set_cached(key, {"items": []}, 60, tags, redis=redis)
        return []

    items = await get_standard_groups(conn, ids, redis, bypass_cache=True)

    await set_cached(
        key,
        {"items": [i.model_dump(mode="json") for i in items]},
        60,
        tags,
        redis=redis,
    )
    return items
