"""Pricing page context — docs + profile identity + evaluated permissions.

Superset of docs.py. A single endpoint that gives the client everything
it needs to render the pricing page:
  1. resolve_profile_identity_context — who you are (name, role, departments)
  2. Entry docs — pricing entry schema introspection (same as docs.py)
  3. Permission evaluation — concrete booleans for THIS caller
  4. Page metadata — titles and descriptions for list/detail/new views
"""

from __future__ import annotations

import asyncio
from uuid import UUID

import asyncpg
from redis.asyncio import Redis

from app.infra.docs.build_profile_summary import build_profile_summary
from app.infra.docs.get_operation_info import get_operation_info
from app.infra.docs.types import (
    CallerPermissions,
    ComposedContextResponse,
    OperationPrompts,
    StarterPrompt,
)
from app.infra.docs_helper import PageMetadataConfig, compute_docs_metadata
from app.infra.profile_identity_context import resolve_profile_identity_context

# Entry tool docs
from app.tools.entries.run_pricing.docs import get_run_pricing_docs
from app.utils.cache.big import (
    DEFAULT_BIG_CACHE_TTL_S,
    big_cache_key,
    get_or_build,
)

_PAGE_METADATA = PageMetadataConfig(
    list_title="Pricing",
    list_description="Track AI model usage costs and trends.",
    detail_title="Pricing",
    detail_description="View pricing analytics with cost breakdowns.",
    new_title="Pricing",
    new_description="View pricing analytics with cost breakdowns.",
)


async def page_context_pricing_impl(
    pool: asyncpg.Pool,
    redis: Redis,
    *,
    profile_id: UUID,
    entity_id: UUID | None = None,
    bypass_cache: bool = False,
    **_kwargs,
) -> ComposedContextResponse:
    """pricing page context — big-cache wrapped."""
    return await get_or_build(
        redis=redis,
        key=big_cache_key("pricing/page_context", {
            "profile_id": str(profile_id),
            "entity_id": str(entity_id) if entity_id else None,
        }),
        tags=["context", "pricing", "artifacts"],
        ttl_s=DEFAULT_BIG_CACHE_TTL_S,
        response_model=ComposedContextResponse,
        builder=lambda: _page_context_pricing_build(
            pool, redis,
            profile_id=profile_id,
            entity_id=entity_id,
        ),
        bypass_cache=bypass_cache,
    )


async def _page_context_pricing_build(
    pool: asyncpg.Pool,
    redis: Redis,
    *,
    profile_id: UUID,
    entity_id: UUID | None = None,
) -> ComposedContextResponse:
    """Pricing page context.

    Flow:
      1. resolve_profile_identity_context -> profile identity (kept, not discarded)
      2. Parallel: entry docs fetch
      3. Evaluate caller permissions using profile data
      4. Assemble ComposedContextResponse
    """
    from fastapi import HTTPException

    # -- Step 1: Profile context ------------------------------------------------

    profile = await resolve_profile_identity_context(pool, profile_id, redis)

    if profile is None:
        raise HTTPException(
            status_code=401,
            detail="Profile not found. Please sign in again.",
        )

    # -- Step 2: Parallel docs fetches ------------------------------------------

    async def _fetch_run_pricing_docs() -> object:
        async with pool.acquire() as c:
            return await get_run_pricing_docs(c)

    (run_pricing,) = await asyncio.gather(
        _fetch_run_pricing_docs(),
    )

    # -- Step 3: Page metadata --------------------------------------------------

    page_metadata = compute_docs_metadata(_PAGE_METADATA)

    # -- Step 4: Evaluate caller permissions ------------------------------------
    # Pricing has no artifact-level permissions module; use simple role defaults.

    caller_permissions = CallerPermissions(
        can_create=False,
        can_draft=False,
        can_duplicate=False,
    )

    # -- Step 5: Build profile summary ------------------------------------------

    profile_summary = await build_profile_summary(pool, redis, profile)

    # -- Step 6: Starter prompts --------------------------------------------------

    prompts = OperationPrompts(prompts={
        "get": [
            StarterPrompt(title="View costs", content="Show AI model usage costs and token breakdowns for the current period."),
            StarterPrompt(title="Check spending", content="Display cost trends and identify the highest-cost simulations."),
        ],
        "search": [
            StarterPrompt(title="Find expensive runs", content="Search for the highest-cost simulation runs over a time period."),
            StarterPrompt(title="Compare models", content="Search pricing data to compare costs across different AI models."),
            StarterPrompt(title="Filter by date", content="Search pricing history filtered by date range and cost threshold."),
        ],
        "export": [
            StarterPrompt(title="Export pricing", content="Export pricing data with cost breakdowns as CSV."),
            StarterPrompt(title="Download costs", content="Generate a downloadable cost analysis report for billing review."),
        ],
        "refresh": [
            StarterPrompt(title="Refresh pricing", content="Refresh pricing materialized views with the latest usage data."),
            StarterPrompt(title="Update costs", content="Rebuild pricing analytics to include recently completed runs."),
        ],
    })

    # -- Step 7: Assemble response ----------------------------------------------

    # Lazy imports to avoid circular dependencies
    from app.routes.system.pricing.export import export_pricing
    from app.routes.system.pricing.get import get_pricing
    from app.routes.system.pricing.refresh import pricing_refresh
    from app.routes.system.pricing.search import search_pricing

    return ComposedContextResponse(
        name="pricing",
        type="analytics",
        description=(
            "Pricing analytics tracks AI model usage costs, run pricing "
            "breakdowns, and cost trends across simulations."
        ),
        entries=[run_pricing],
        resources=[],
        permission_docs=[],
        api_operations=[
            get_operation_info(
                get_pricing,
                description="POST /get — Get pricing analytics with cost breakdowns.",
            ),
            get_operation_info(
                search_pricing,
                description="POST /search — Search pricing history entries.",
            ),
            get_operation_info(
                pricing_refresh,
                description="POST /refresh — Refresh pricing materialized views.",
            ),
            get_operation_info(
                export_pricing,
                description="POST /export — Export pricing data as CSV/ZIP.",
            ),
        ],
        page_metadata=page_metadata,
        prompts=prompts,
        profile=profile_summary,
        caller_permissions=caller_permissions,
    )
