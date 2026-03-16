"""Shared pricing computation helpers for pricing-related infra packages."""

from decimal import Decimal
from uuid import UUID

import asyncpg

from app.infra.globals import get_redis_client
from app.tools.entries.runs.search import RunViewItem
from app.utils.cache.cache_key import cache_key
from app.utils.cache.get_cached import get_cached
from app.utils.cache.set_cached import set_cached


class PricingInfo:
    """Price and unit value for a single pricing resource row."""

    __slots__ = ("price", "unit_value")

    def __init__(self, price: Decimal, unit_value: int) -> None:
        self.price = price
        self.unit_value = unit_value


async def _batch_fetch_pricing(
    conn: asyncpg.Connection,
    pricing_ids: list[UUID],
    bypass_cache: bool = False,
) -> dict[UUID, PricingInfo]:
    """Batch fetch pricing_resource price and unit_value by IDs."""
    if not pricing_ids:
        return {}

    cache_key_val = cache_key(
        "_shared/pricing/batch",
        {"ids": sorted(str(p) for p in pricing_ids)},
    )

    if not bypass_cache:
        cached = await get_cached(cache_key_val, redis=get_redis_client())
        if cached:
            return {
                UUID(k): PricingInfo(Decimal(str(v["price"])), v["unit_value"])
                for k, v in cached.items()
            }

    rows = await conn.fetch(
        "SELECT id, price, unit_value FROM pricing_resource WHERE id = ANY($1) AND active = TRUE",
        pricing_ids,
    )
    result = {
        row["id"]: PricingInfo(Decimal(str(row["price"])), row["unit_value"])
        for row in rows
    }

    await set_cached(
        cache_key_val,
        {
            str(key): {"price": str(value.price), "unit_value": value.unit_value}
            for key, value in result.items()
        },
        ttl=300,
        tags=["_shared", "pricing"],
        redis=get_redis_client(),
    )

    return result


async def compute_costs_from_runs(
    conn: asyncpg.Connection,
    runs: list[RunViewItem],
    bypass_cache: bool = False,
) -> dict[UUID, Decimal]:
    """Compute per-run cost from RunViewItem.pricing data."""
    if not runs:
        return {}

    all_pricing_ids: set[UUID] = set()
    for run in runs:
        for pricing in run.pricing:
            if pricing.pricing_id:
                all_pricing_ids.add(pricing.pricing_id)

    pricing_map: dict[UUID, PricingInfo] = {}
    if all_pricing_ids:
        pricing_map = await _batch_fetch_pricing(
            conn, list(all_pricing_ids), bypass_cache
        )

    result: dict[UUID, Decimal] = {}
    for run in runs:
        total_cost = Decimal("0")
        for pricing in run.pricing:
            if pricing.pricing_id and pricing.count:
                info = pricing_map.get(pricing.pricing_id)
                if info and info.unit_value > 0:
                    total_cost += (
                        Decimal(str(pricing.count)) / Decimal(str(info.unit_value))
                    ) * info.price
        result[run.run_id] = total_cost

    return result
