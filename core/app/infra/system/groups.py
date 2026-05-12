"""Top-level paginated groups list with cost aggregation.

Resolves a pricing-search context (groups + total_groups + runs +
pricing/name resources), applies in-memory model/profile/agent filters,
aggregates per-group run stats (counts, tokens, cost windows), and
returns a paginated ``ListPricingResponse``.

Pricing data travels alongside as the canonical shape — the endpoint is
fundamentally "search groups" and other consumers (group browsers,
GenerationPanel history) call this rather than per-artifact search.

Routes/system/groups.py is a thin HTTP adapter over
``groups_system_impl`` that adds the caching layer.
"""

from __future__ import annotations

from collections import defaultdict
from decimal import Decimal
from uuid import UUID

import asyncpg
from redis.asyncio import Redis

from app.infra.common_context import resolve_common_context
from app.infra.pricing.context import resolve_pricing_search_context
from app.infra.pricing.types import (
    ListPricingRequest,
    ListPricingResponse,
    PricingGroupItem,
)


class ProfileNotFoundError(LookupError):
    """Raised when resolve_common_context cannot find the profile."""


async def groups_system_impl(
    pool: asyncpg.Pool,
    redis: Redis,
    *,
    profile_id: UUID,
    session_id: UUID,
    request: ListPricingRequest,
    bypass_cache: bool = False,
) -> ListPricingResponse:
    """Paginated groups list with per-group run/cost aggregation.

    Args:
        pool: asyncpg pool.
        redis: Redis client (used for downstream context caches; this
            function does NOT cache its own response — the route adapter
            handles that to keep cache-key + header concerns at the HTTP
            edge).
        profile_id: Caller's profile UUID.
        session_id: Caller's session UUID. Used as the scope for context
            resolution.
        request: Body of the search.
        bypass_cache: If True, downstream context caches are skipped.

    Returns:
        ``ListPricingResponse`` ready to send.

    Raises:
        ProfileNotFoundError: profile cannot be resolved.
    """
    # --- Phase 0: Resolve common context (profile identity) ---
    common = await resolve_common_context(
        pool, redis, profile_id=profile_id, bypass_cache=bypass_cache,
    )
    if not common:
        raise ProfileNotFoundError("Profile not found")

    # --- Phase 1: Resolve pricing search context ---
    ctx = await resolve_pricing_search_context(
        pool,
        redis,
        session_ids=[session_id],
        department_ids=request.department_ids or None,
        name_search=request.search,
        date_from=request.effective_date_from,
        date_to=request.effective_date_to,
        sort_order=request.sort_order,
        page=request.page,
        page_size=request.page_size,
        bypass_cache=bypass_cache,
    )

    # --- Phase 2: Extract data ---
    groups = ctx.entries.get("groups", [])
    total_groups = ctx.entries.get("total_groups", [])
    runs = ctx.entries.get("runs", [])

    # --- Phase 2a: Apply in-memory filters (model/profile/agent) ---
    # Multi-model wins over legacy singular ``model_id``.
    model_id_filter: set[UUID] = set()
    if request.model_ids:
        model_id_filter.update(request.model_ids)
    elif request.model_id:
        model_id_filter.add(request.model_id)
    profile_id_filter: set[UUID] = set(request.profile_ids or [])
    agent_id_filter: set[UUID] = set(request.agent_ids or [])

    if model_id_filter or profile_id_filter or agent_id_filter:
        def _run_matches(run) -> bool:  # noqa: ANN001 — local closure
            if model_id_filter and not any(
                mid in model_id_filter for mid in (run.model_ids or [])
            ):
                return False
            if profile_id_filter and run.profiles_id not in profile_id_filter:
                return False
            if agent_id_filter and not any(
                aid in agent_id_filter for aid in (run.agent_ids or [])
            ):
                return False
            return True

        matching_group_ids = {
            run.group_id for run in runs if run.group_id and _run_matches(run)
        }
        groups = [g for g in groups if g.id in matching_group_ids]
        total_groups = [g for g in total_groups if g.id in matching_group_ids]
        runs = [r for r in runs if r.group_id in matching_group_ids]

    pricing_rp = ctx.resources.get("pricing")
    pricing_list = pricing_rp.selected if pricing_rp else []
    names_rp = ctx.resources.get("names")
    name_list = names_rp.selected if names_rp else []

    # --- Phase 3: Build pricing map + name map ---
    pricing_map: dict[UUID, dict] = {}
    for p in pricing_list:
        if p.id:
            pricing_map[p.id] = {
                "price": Decimal(str(p.price)) if p.price is not None else Decimal("0"),
                "unit_value": p.unit_value or 1,
            }

    name_map = {item.id: item.name for item in name_list if item.id and item.name}

    # --- Phase 4: Aggregate runs per group ---
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
            "profile_ids": set(),
        }
    )

    for run in runs:
        gid = run.group_id
        if not gid:
            continue
        stats = group_stats[gid]
        stats["run_count"] += 1
        stats["total_input_tokens"] += run.input_tokens
        stats["total_output_tokens"] += run.output_tokens
        stats["total_tokens"] += (
            run.input_tokens + run.output_tokens + run.cached_input_tokens
        )

        run_cost = Decimal("0")
        for p in run.pricing:
            if p.pricing_id and p.count:
                info = pricing_map.get(p.pricing_id)
                if info and info["unit_value"] > 0:
                    run_cost += (
                        Decimal(str(p.count)) / Decimal(str(info["unit_value"]))
                    ) * info["price"]
        stats["total_cost"] += run_cost

        if run.run_created_at:
            if (
                stats["first_run_at"] is None
                or run.run_created_at < stats["first_run_at"]
            ):
                stats["first_run_at"] = run.run_created_at
            if (
                stats["last_run_at"] is None
                or run.run_created_at > stats["last_run_at"]
            ):
                stats["last_run_at"] = run.run_created_at
        if run.agent_ids:
            stats["agent_ids"].update(run.agent_ids)
        if run.model_ids:
            stats["model_ids"].update(run.model_ids)
        if run.profiles_id:
            stats["profile_ids"].add(run.profiles_id)

    # --- Phase 5: Build group items ---
    items: list[PricingGroupItem] = []
    for group in groups:
        gid = group.id
        stats = group_stats.get(gid, {})

        agent_id_list = list(stats.get("agent_ids", set()))
        model_id_list = list(stats.get("model_ids", set()))
        profile_id_list = list(stats.get("profile_ids", set()))
        a_names = [
            name_map[aid] for aid in agent_id_list if aid in name_map
        ] or None
        m_names = [
            name_map[mid] for mid in model_id_list if mid in name_map
        ] or None

        items.append(
            PricingGroupItem(
                group_id=gid,
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
                profile_ids=profile_id_list or None,
                agent_names=a_names,
                model_names=m_names,
            )
        )

    # --- Phase 5a: Apply explicit sort (search_groups orders by date desc) ---
    sort_key = (request.sort_by or "date").lower()
    reverse = (request.sort_order or "desc").lower() != "asc"
    if sort_key == "total_cost":
        items.sort(key=lambda i: i.total_cost, reverse=reverse)
    elif sort_key == "total_tokens":
        items.sort(key=lambda i: i.total_tokens, reverse=reverse)
    elif sort_key == "run_count":
        items.sort(key=lambda i: i.run_count, reverse=reverse)
    elif sort_key in ("date", "first_run_at", "last_run_at"):
        if not reverse:
            items.reverse()

    total_count = len(total_groups)
    page_size = request.page_size
    total_pages = (total_count + page_size - 1) // page_size if page_size > 0 else 0

    return ListPricingResponse(
        data=items,
        total_count=total_count,
        page=request.page,
        page_size=page_size,
        total_pages=total_pages,
    )
