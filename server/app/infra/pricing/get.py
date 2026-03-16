"""Canonical shared pricing GET operation."""

from __future__ import annotations

import asyncio
from decimal import Decimal
from uuid import UUID

from fastapi import HTTPException
from redis.asyncio import Redis

from app.infra.analytics_facets import (
    HIDDEN,
    VISIBLE,
    AnalyticsFacetsConfig,
    resolve_analytics_facets,
)
from app.infra.common_context import resolve_common_context
from app.infra.pricing.context import resolve_pricing_context
from app.infra.auth.types import AnalyticsFilterFields
from app.infra.pricing.types import (
    PricingDailyItem,
    PricingRequest,
    PricingResources,
    PricingResponse,
)
from app.infra.v5_types import FilterOption

PRICING_FACETS_CONFIG = AnalyticsFacetsConfig(
    fields=AnalyticsFilterFields(
        date_range=VISIBLE,
        departments=VISIBLE,
        cohorts=HIDDEN,
        roles=HIDDEN,
        attempts=HIDDEN,
    ),
    mv_source="pricing",
)


def _compute_run_costs(
    runs: list,
    pricing_map: dict[UUID, dict],
) -> dict[UUID, Decimal]:
    """Compute per-run cost from inline pricing entries + pricing resource data."""
    result: dict[UUID, Decimal] = {}
    for run in runs:
        total_cost = Decimal("0")
        for pricing in run.pricing:
            if pricing.pricing_id and pricing.count:
                info = pricing_map.get(pricing.pricing_id)
                if info and info["unit_value"] > 0:
                    total_cost += (
                        Decimal(str(pricing.count)) / Decimal(str(info["unit_value"]))
                    ) * info["price"]
        result[run.run_id] = total_cost
    return result


async def get_pricing_impl(
    pool,
    redis: Redis,
    *,
    profile_id: UUID,
    request: PricingRequest,
    bypass_cache: bool = False,
) -> PricingResponse:
    """Resolve the canonical pricing top-chart response for any surface."""
    common = await resolve_common_context(
        pool,
        redis,
        profile_id=profile_id,
        bypass_cache=bypass_cache,
    )
    if not common:
        raise HTTPException(status_code=401, detail="Profile not found")

    ctx, analytics_facets = await asyncio.gather(
        resolve_pricing_context(
            pool,
            redis,
            date_from=request.effective_date_from,
            date_to=request.effective_date_to,
            bypass_cache=bypass_cache,
        ),
        resolve_analytics_facets(
            pool,
            redis,
            config=PRICING_FACETS_CONFIG,
            profile=common.profile,
            bypass_cache=bypass_cache,
        ),
    )

    runs = ctx.entries.get("runs", [])
    agent_list = (
        ctx.resources.get("agents").selected if ctx.resources.get("agents") else []
    )
    model_list = (
        ctx.resources.get("models").selected if ctx.resources.get("models") else []
    )
    pricing_list = (
        ctx.resources.get("pricing").selected if ctx.resources.get("pricing") else []
    )

    pricing_map: dict[UUID, dict] = {}
    for pricing in pricing_list:
        if pricing.id:
            pricing_map[pricing.id] = {
                "price": Decimal(str(pricing.price))
                if pricing.price is not None
                else Decimal("0"),
                "unit_value": pricing.unit_value or 1,
            }

    run_costs = _compute_run_costs(runs, pricing_map)

    daily_buckets: dict[tuple[str, str | None], dict] = {}
    for run in runs:
        date_key = (
            run.run_created_at.strftime("%Y-%m-%d") if run.run_created_at else "unknown"
        )
        model_id = str(run.model_ids[0]) if run.model_ids else None
        bucket_key = (date_key, model_id)
        if bucket_key not in daily_buckets:
            daily_buckets[bucket_key] = {"total_cost": Decimal("0"), "run_count": 0}
        daily_buckets[bucket_key]["total_cost"] += run_costs.get(
            run.run_id, Decimal("0")
        )
        daily_buckets[bucket_key]["run_count"] += 1

    daily_items = [
        PricingDailyItem(
            date_key=date_key,
            model_id=model_id,
            total_cost=bucket["total_cost"],
            run_count=bucket["run_count"],
        )
        for (date_key, model_id), bucket in sorted(
            daily_buckets.items(), key=lambda item: (item[0][0], item[0][1] or "")
        )
    ]

    agent_map = {
        str(agent.id): {"name": agent.name} for agent in agent_list if agent.id
    }
    model_map = {
        str(model.id): {"name": model.name} for model in model_list if model.id
    }
    model_options = [
        FilterOption(value=str(model.id), label=model.name)
        for model in model_list
        if model.id
    ]
    agent_options = [
        FilterOption(value=str(agent.id), label=agent.name)
        for agent in agent_list
        if agent.id
    ]

    return PricingResponse(
        daily=daily_items,
        resources=PricingResources(agents=agent_map, models=model_map),
        total_count=len(runs),
        model_options=model_options,
        agent_options=agent_options,
        analytics=analytics_facets,
    )
