"""Canonical shared pricing GET operation."""

from __future__ import annotations

import asyncio
from collections import defaultdict
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
from app.infra.api_types import FilterOption
from app.infra.auth.types import AnalyticsFilterFields
from app.infra.common_context import resolve_common_context
from app.infra.pricing.context import (
    resolve_pricing_context,
    resolve_pricing_search_context,
)
from app.infra.pricing.types import (
    PricingDailyItem,
    PricingGroupItem,
    PricingHistoryResponse,
    PricingRequest,
    PricingResources,
    PricingResponse,
)

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


async def _build_pricing_history(
    pool,
    redis: Redis,
    request: PricingRequest,
    *,
    session_id: UUID | None = None,
    bypass_cache: bool = False,
) -> PricingHistoryResponse:
    ctx = await resolve_pricing_search_context(
        pool,
        redis,
        session_ids=[session_id] if session_id else None,
        date_from=request.effective_date_from,
        date_to=request.effective_date_to,
        sort_order=request.history_sort_order,
        page=request.history_page,
        page_size=request.history_page_size,
        bypass_cache=bypass_cache,
    )

    groups = ctx.entries.get("groups", [])
    total_groups = ctx.entries.get("total_groups", [])
    runs = ctx.entries.get("runs", [])

    if request.history_model_id:
        matching_group_ids = {
            run.group_id
            for run in runs
            if run.group_id and request.history_model_id in (run.model_ids or [])
        }
        groups = [group for group in groups if group.id in matching_group_ids]
        total_groups = [
            group for group in total_groups if group.id in matching_group_ids
        ]
        runs = [run for run in runs if run.group_id in matching_group_ids]

    pricing_rp = ctx.resources.get("pricing")
    pricing_list = pricing_rp.selected if pricing_rp else []
    names_rp = ctx.resources.get("names")
    name_list = names_rp.selected if names_rp else []

    pricing_map: dict[UUID, dict] = {}
    for pricing in pricing_list:
        if pricing.id:
            pricing_map[pricing.id] = {
                "price": Decimal(str(pricing.price))
                if pricing.price is not None
                else Decimal("0"),
                "unit_value": pricing.unit_value or 1,
            }

    name_map = {item.id: item.name for item in name_list if item.id and item.name}

    group_stats: dict[UUID, dict] = defaultdict(
        lambda: {
            "run_count": 0,
            "total_input_tokens": 0,
            "total_output_tokens": 0,
            "total_tokens": 0,
            "total_cost": Decimal("0"),
            "first_run_at": None,
            "last_run_at": None,
            "agent_ids": set(),
            "model_ids": set(),
        }
    )

    for run in runs:
        group_id = run.group_id
        if not group_id:
            continue
        stats = group_stats[group_id]
        stats["run_count"] += 1
        stats["total_input_tokens"] += run.input_tokens
        stats["total_output_tokens"] += run.output_tokens
        stats["total_tokens"] += (
            run.input_tokens + run.output_tokens + run.cached_input_tokens
        )

        run_cost = Decimal("0")
        for pricing in run.pricing:
            if pricing.pricing_id and pricing.count:
                info = pricing_map.get(pricing.pricing_id)
                if info and info["unit_value"] > 0:
                    run_cost += (
                        Decimal(str(pricing.count)) / Decimal(str(info["unit_value"]))
                    ) * info["price"]
        stats["total_cost"] += run_cost

        if run.run_created_at:
            if stats["first_run_at"] is None or run.run_created_at < stats["first_run_at"]:
                stats["first_run_at"] = run.run_created_at
            if stats["last_run_at"] is None or run.run_created_at > stats["last_run_at"]:
                stats["last_run_at"] = run.run_created_at
        if run.agent_ids:
            stats["agent_ids"].update(run.agent_ids)
        if run.model_ids:
            stats["model_ids"].update(run.model_ids)

    items: list[PricingGroupItem] = []
    for group in groups:
        stats = group_stats.get(group.id, {})
        agent_id_list = list(stats.get("agent_ids", set()))
        model_id_list = list(stats.get("model_ids", set()))
        items.append(
            PricingGroupItem(
                group_id=group.id,
                session_id=group.session_id,
                group_name=group.name,
                first_run_at=stats.get("first_run_at"),
                last_run_at=stats.get("last_run_at"),
                run_count=stats.get("run_count", 0),
                total_input_tokens=stats.get("total_input_tokens", 0),
                total_output_tokens=stats.get("total_output_tokens", 0),
                total_tokens=stats.get("total_tokens", 0),
                total_cost=stats.get("total_cost", Decimal("0")),
                agent_ids=agent_id_list or None,
                model_ids=model_id_list or None,
                agent_names=[
                    name_map[agent_id]
                    for agent_id in agent_id_list
                    if agent_id in name_map
                ]
                or None,
                model_names=[
                    name_map[model_id]
                    for model_id in model_id_list
                    if model_id in name_map
                ]
                or None,
            )
        )

    total_count = len(total_groups)
    page_size = request.history_page_size
    total_pages = (total_count + page_size - 1) // page_size if page_size > 0 else 0
    return PricingHistoryResponse(
        items=items,
        total_count=total_count,
        page=request.history_page,
        page_size=page_size,
        total_pages=total_pages,
    )


async def get_pricing_impl(
    pool,
    redis: Redis,
    *,
    profile_id: UUID,
    session_id: UUID | None = None,
    request: PricingRequest | None = None,
    bypass_cache: bool = False,
    **_kwargs,
) -> PricingResponse:
    """Resolve the canonical pricing top-chart response for any surface.

    ``request`` is optional — when omitted (e.g. tool-dispatch path that
    only knows flat kwargs) it's reconstructed from ``_kwargs`` against
    ``PricingRequest``'s declared fields. Direct callers (routes, ws)
    keep passing the pre-built request as before.
    """
    if request is None:
        request = PricingRequest(**{
            k: v for k, v in _kwargs.items() if k in PricingRequest.model_fields
        })
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
        history=await _build_pricing_history(
            pool,
            redis,
            request,
            session_id=session_id,
            bypass_cache=bypass_cache,
        ),
    )
