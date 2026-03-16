"""Request Limits SEARCH — reusable data-access layer."""

from uuid import UUID

import asyncpg  # type: ignore
from redis.asyncio import Redis

from app.infra.search.search_resource import search_resource_ids
from app.tools.resources.request_limits.get import get_request_limits
from app.tools.resources.request_limits.types import (
    GetRequestLimitResponse,
)
from app.utils.cache.cache_key import cache_key
from app.utils.cache.get_cached import get_cached
from app.utils.cache.set_cached import set_cached

JUNCTION_ARTIFACTS = ["profile"]


async def search_request_limits(
    conn: asyncpg.Connection,
    redis: Redis,
    search: str | None = None,
    limit_count: int = 20,
    offset_count: int = 0,
    exclude_ids: list[UUID] | None = None,
    bypass_cache: bool = False,
    *,
    profile: bool = False,
) -> list[GetRequestLimitResponse]:
    """Search request limits with optional artifact filters."""
    if limit_count <= 0:
        return []

    artifact_filters = {
        "profile": profile,
    }

    extra_conditions: list[tuple[str, object]] = [
        ("{alias}.active = ${idx}::boolean", True),
    ]

    tags = ["resources", "request_limits"]
    key = cache_key(
        "/v5/resources/request_limits/search",
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
                GetRequestLimitResponse.model_validate(item)
                for item in cached.get("items", [])
            ]

    ids = await search_resource_ids(
        conn,
        table="request_limits_resource",
        resource="request_limits",
        search_column=None,
        search=None,
        limit_count=limit_count,
        offset_count=offset_count,
        exclude_ids=exclude_ids,
        artifact_filters=artifact_filters,
        junction_artifacts=JUNCTION_ARTIFACTS,
        order_column="requests_per_day",
        extra_conditions=extra_conditions,
    )

    if not ids:
        await set_cached(key, {"items": []}, 60, tags, redis=redis)
        return []

    items = await get_request_limits(conn, ids, redis, bypass_cache=True)

    await set_cached(
        key,
        {"items": [i.model_dump(mode="json") for i in items]},
        60,
        tags,
        redis=redis,
    )
    return items
