"""Model Positions SEARCH — reusable data-access layer."""

from uuid import UUID

import asyncpg  # type: ignore
from redis.asyncio import Redis

from app.infra.search.search_resource import search_resource_ids
from app.tools.resources.model_positions.get import get_model_positions
from app.tools.resources.model_positions.types import GetModelPositionResponse
from app.utils.cache.cache_key import cache_key
from app.utils.cache.get_cached import get_cached
from app.utils.cache.set_cached import set_cached

JUNCTION_ARTIFACTS = ["eval"]


async def search_model_positions(
    conn: asyncpg.Connection,
    redis: Redis,
    limit_count: int = 20,
    offset_count: int = 0,
    exclude_ids: list[UUID] | None = None,
    model_ids: list[UUID] | None = None,
    bypass_cache: bool = False,
    *,
    eval: bool = False,
) -> list[GetModelPositionResponse]:
    """Search model positions with optional artifact filters."""
    if limit_count <= 0:
        return []

    artifact_filters = {"eval": eval}

    extra_conditions: list[tuple[str, object]] = []
    if model_ids:
        extra_conditions.append(("{alias}.model_id = ANY(${idx})", model_ids))

    tags = ["resources", "model_positions"]
    key = cache_key(
        "/v5/resources/model_positions/search",
        {
            "limit_count": limit_count,
            "offset_count": offset_count,
            "exclude_ids": [str(i) for i in (exclude_ids or [])],
            "model_ids": sorted(str(i) for i in (model_ids or [])),
            **artifact_filters,
        },
    )

    if not bypass_cache:
        cached = await get_cached(key, redis=redis)
        if cached:
            return [
                GetModelPositionResponse.model_validate(item)
                for item in cached.get("items", [])
            ]

    ids = await search_resource_ids(
        conn,
        table="model_positions_resource",
        resource="model_positions",
        search_column=None,
        order_column="value",
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

    items = await get_model_positions(conn, ids, redis, bypass_cache=True)

    await set_cached(
        key,
        {"items": [i.model_dump(mode="json") for i in items]},
        60,
        tags,
        redis=redis,
    )
    return items
