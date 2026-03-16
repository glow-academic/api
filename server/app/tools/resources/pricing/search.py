"""Pricing SEARCH — reusable data-access layer."""

from uuid import UUID

import asyncpg  # type: ignore
from redis.asyncio import Redis

from app.infra.search.search_resource import search_resource_ids
from app.tools.resources.pricing.get import get_pricing
from app.tools.resources.pricing.types import GetPricingResponse
from app.utils.cache.cache_key import cache_key
from app.utils.cache.get_cached import get_cached
from app.utils.cache.set_cached import set_cached

JUNCTION_ARTIFACTS = ["model"]


async def search_pricing(
    conn: asyncpg.Connection,
    redis: Redis,
    search: str | None = None,
    limit_count: int = 20,
    offset_count: int = 0,
    exclude_ids: list[UUID] | None = None,
    pricing_type: str | None = None,
    unit_names: list[str] | None = None,
    bypass_cache: bool = False,
    *,
    model: bool = False,
) -> list[GetPricingResponse]:
    """Search pricing with optional artifact filters."""
    if limit_count <= 0:
        return []

    artifact_filters = {"model": model}

    extra_conditions: list[tuple[str, object]] = []
    if pricing_type is not None:
        extra_conditions.append(("{alias}.pricing_type::text = ${idx}", pricing_type))
    if unit_names:
        extra_conditions.append(
            (
                "(COALESCE(array_length(${idx}::text[], 1), 0) = 0 OR {alias}.unit_name = ANY(${idx}::text[]))",
                unit_names,
            )
        )

    tags = ["resources", "pricing"]
    key = cache_key(
        "/v5/resources/pricing/search",
        {
            "search": search,
            "limit_count": limit_count,
            "offset_count": offset_count,
            "exclude_ids": [str(i) for i in (exclude_ids or [])],
            "pricing_type": pricing_type,
            "unit_names": sorted(unit_names or []),
            **artifact_filters,
        },
    )

    if not bypass_cache:
        cached = await get_cached(key, redis=redis)
        if cached:
            return [
                GetPricingResponse.model_validate(item)
                for item in cached.get("items", [])
            ]

    ids = await search_resource_ids(
        conn,
        table="pricing_resource",
        resource="pricing",
        search_column="pricing_type::text",
        search=search,
        limit_count=limit_count,
        offset_count=offset_count,
        exclude_ids=exclude_ids,
        artifact_filters=artifact_filters,
        junction_artifacts=JUNCTION_ARTIFACTS,
        order_column="id",
        extra_conditions=extra_conditions if extra_conditions else None,
    )

    if not ids:
        await set_cached(key, {"items": []}, 60, tags, redis=redis)
        return []

    items = await get_pricing(conn, ids, redis, bypass_cache=True)

    await set_cached(
        key,
        {"items": [i.model_dump(mode="json") for i in items]},
        60,
        tags,
        redis=redis,
    )
    return items
