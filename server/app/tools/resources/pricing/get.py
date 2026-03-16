"""Pricing Resource GET — reusable data-access layer."""

from uuid import UUID

import asyncpg  # type: ignore
from redis.asyncio import Redis

from app.tools.resources.pricing.types import GetPricingResponse
from app.utils.cache.cache_key import cache_key
from app.utils.cache.get_cached import get_cached
from app.utils.cache.set_cached import set_cached


async def get_pricing(
    conn: asyncpg.Connection,
    ids: list[UUID],
    redis: Redis,
    bypass_cache: bool = False,
) -> list[GetPricingResponse]:
    """Fetch pricing_resource entries by IDs."""
    if not ids:
        return []

    tags = ["resources", "pricing"]
    key = cache_key("/v5/resources/pricing/get", {"ids": [str(id) for id in ids]})

    if not bypass_cache:
        cached = await get_cached(key, redis=redis)
        if cached:
            return [
                GetPricingResponse.model_validate(item)
                for item in cached.get("items", [])
            ]

    rows = await conn.fetch(
        """
        SELECT id, pricing_type, price,
               unit_name, unit_category, unit_value,
               created_at, active, mcp, generated
        FROM pricing_resource
        WHERE id = ANY($1)
        ORDER BY array_position($1, id)
    """,
        ids,
    )

    items = [
        GetPricingResponse(
            id=r["id"],
            pricing_type=r["pricing_type"],
            price=r["price"],
            unit_name=r["unit_name"],
            unit_category=r["unit_category"],
            unit_value=r["unit_value"],
            created_at=r["created_at"],
            active=r["active"],
            mcp=r["mcp"],
            generated=r["generated"],
        )
        for r in rows
    ]

    if not bypass_cache:
        await set_cached(
            key,
            {"items": [i.model_dump(mode="json") for i in items]},
            60,
            tags,
            redis=redis,
        )
    return items
