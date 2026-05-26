"""Dashboard page context — docs + profile identity + evaluated permissions.

Superset of docs.py. A single endpoint that gives the client everything
it needs to render the dashboard page:
  1. resolve_profile_identity_context — who you are (name, role, departments)
  2. Permission evaluation — concrete booleans for THIS caller
  3. API operations — all public route handlers introspected
  4. Page metadata — titles and descriptions for list/detail/new views
"""

from __future__ import annotations

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
from app.infra.server_timing import timed
from app.utils.cache.big import (
    DEFAULT_BIG_CACHE_TTL_S,
    big_cache_key,
    get_or_build,
)

_PAGE_METADATA = PageMetadataConfig(
    list_title="Dashboard",
    list_description="View aggregated performance metrics and trends.",
    detail_title="Dashboard",
    detail_description="View dashboard analytics with metrics and sections.",
    new_title="Dashboard",
    new_description="View aggregated performance metrics and trends.",
)


async def page_context_dashboard_impl(
    pool: asyncpg.Pool,
    redis: Redis,
    *,
    profile_id: UUID,
    entity_id: UUID | None = None,
    schema: bool = False,
    bypass_cache: bool = False,
    **_kwargs,
) -> ComposedContextResponse:
    """dashboard page context — big-cache wrapped."""
    return await get_or_build(
        redis=redis,
        key=big_cache_key("dashboard/page_context", {
            "profile_id": str(profile_id),
            "entity_id": str(entity_id) if entity_id else None,
            "schema": schema,
        }),
        tags=["context", "dashboard", "artifacts"],
        ttl_s=DEFAULT_BIG_CACHE_TTL_S,
        response_model=ComposedContextResponse,
        builder=lambda: _page_context_dashboard_build(
            pool, redis,
            profile_id=profile_id,
            entity_id=entity_id,
            schema=schema,
        ),
        bypass_cache=bypass_cache,
    )


async def _page_context_dashboard_build(
    pool: asyncpg.Pool,
    redis: Redis,
    *,
    profile_id: UUID,
    entity_id: UUID | None = None,
    schema: bool = False,
) -> ComposedContextResponse:
    """Dashboard page context.

    Flow:
      1. resolve_profile_identity_context -> profile identity (kept, not discarded)
      2. Evaluate caller permissions using profile data
      3. Assemble ComposedContextResponse
    """
    from fastapi import HTTPException

    # -- Step 1: Profile context ------------------------------------------------

    with timed("profile"):
        profile = await resolve_profile_identity_context(pool, profile_id, redis)

    if profile is None:
        raise HTTPException(
            status_code=401,
            detail="Profile not found. Please sign in again.",
        )

    # -- Step 2: Page metadata --------------------------------------------------

    page_metadata = compute_docs_metadata(_PAGE_METADATA)

    # -- Step 3: Evaluate caller permissions ------------------------------------
    # Dashboard is analytics — no entity-level create/draft/duplicate.
    # CallerPermissions still populated for sidebar/nav consistency.

    caller_permissions = CallerPermissions(
        can_create=False,
        can_draft=False,
        can_duplicate=False,
    )

    # -- Step 4: Build profile summary ------------------------------------------

    with timed("profile_summary"):
        profile_summary = await build_profile_summary(pool, redis, profile)

    # -- Step 5: Starter prompts --------------------------------------------------

    prompts = OperationPrompts(prompts={
        "get": [
            StarterPrompt(title="View metrics", content="Show the aggregated performance metrics and section breakdowns for the dashboard."),
            StarterPrompt(title="Analyze trends", content="Highlight key trends and changes in the dashboard's primary metrics."),
            StarterPrompt(title="Spot outliers", content="Identify outlier metrics or sections that need attention."),
        ],
        "search": [
            StarterPrompt(title="Find history", content="Search dashboard history entries to compare metrics over time."),
            StarterPrompt(title="Filter by cohort", content="Search dashboard data filtered by cohort or department."),
        ],
        "export": [
            StarterPrompt(title="Export dashboard", content="Export the current dashboard metrics and sections as CSV."),
            StarterPrompt(title="Download summary", content="Generate a downloadable summary of all dashboard analytics."),
        ],
        "refresh": [
            StarterPrompt(title="Refresh dashboard", content="Refresh dashboard materialized views with the latest data."),
            StarterPrompt(title="Rebuild metrics", content="Rebuild aggregated dashboard metrics from the latest simulation results."),
        ],
    })

    # -- Step 6: Assemble response ----------------------------------------------

    # Lazy imports to avoid circular dependencies
    from app.infra.dashboard.permissions import (
        build_dashboard_bundle,
        compute_footer_metrics,
        compute_header_metrics,
        compute_primary_metrics,
        compute_secondary_metrics,
    )
    from app.routes.attempt.dashboard.export import export_dashboard
    from app.routes.attempt.dashboard import get_dashboard
    from app.routes.attempt.dashboard.refresh import dashboard_refresh
    # /dashboard/search collapsed into canonical /attempt/search endpoint.

    return ComposedContextResponse(
        name="dashboard",
        type="analytics",
        description=(
            "Dashboard analytics provides aggregated performance metrics, "
            "trend analysis, and summary sections across simulations and cohorts."
        ),
        artifact=None,
        entries=([] if schema else None),
        resources=([] if schema else None),
        permission_docs=([
            get_operation_info(
                compute_header_metrics,
                description="Compute header-level aggregated metrics for the dashboard.",
            ),
            get_operation_info(
                compute_primary_metrics,
                description="Compute primary analytics metrics section.",
            ),
            get_operation_info(
                compute_secondary_metrics,
                description="Compute secondary analytics metrics section.",
            ),
            get_operation_info(
                compute_footer_metrics,
                description="Compute footer analytics metrics section.",
            ),
            get_operation_info(
                build_dashboard_bundle,
                description="Build the complete dashboard bundle with all metric sections.",
            ),
        ] if schema else None),
        api_operations=([
            get_operation_info(
                get_dashboard,
                description="POST /get — Get dashboard analytics with metrics and sections.",
            ),
            # /search collapsed into canonical /attempt/search.
            get_operation_info(
                dashboard_refresh,
                description="POST /refresh — Refresh dashboard materialized views.",
            ),
            get_operation_info(
                export_dashboard,
                description="POST /export — Export dashboard data as CSV/ZIP.",
            ),
        ] if schema else None),
        page_metadata=page_metadata,
        prompts=prompts,
        profile=profile_summary,
        caller_permissions=caller_permissions,
    )
