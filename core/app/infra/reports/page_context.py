"""Reports page context — docs + profile identity + evaluated permissions.

Superset of docs.py. A single endpoint that gives the client everything
it needs to render the reports page:
  1. resolve_profile_identity_context — who you are (name, role, departments)
  2. Permission docs — reports section computation functions
  3. Permission evaluation — concrete booleans for THIS caller
  4. Page metadata — titles and descriptions for list/detail/new views
"""

from __future__ import annotations

from uuid import UUID

import asyncpg
from redis.asyncio import Redis

from app.infra.docs.get_operation_info import get_operation_info
from app.infra.docs.types import (
    CallerPermissions,
    ComposedContextResponse,
    OperationPrompts,
    StarterPrompt,
)
from app.infra.docs.build_profile_summary import build_profile_summary
from app.infra.docs_helper import PageMetadataConfig, compute_docs_metadata
from app.infra.profile_identity_context import resolve_profile_identity_context

from app.utils.cache.big import (
    DEFAULT_BIG_CACHE_TTL_S,
    big_cache_key,
    get_or_build,
)

_PAGE_METADATA = PageMetadataConfig(
    list_title="Reports",
    list_description="Generate comprehensive performance reports.",
    detail_title="Reports",
    detail_description="View report analytics with overview and trends.",
    new_title="Reports",
    new_description="View report analytics with overview and trends.",
)


async def page_context_reports_impl(
    pool: asyncpg.Pool,
    redis: Redis,
    *,
    profile_id: UUID,
    entity_id: UUID | None = None,
    bypass_cache: bool = False,
    **_kwargs,
) -> ComposedContextResponse:
    """reports page context — big-cache wrapped."""
    return await get_or_build(
        redis=redis,
        key=big_cache_key("reports/page_context", {
            "profile_id": str(profile_id),
            "entity_id": str(entity_id) if entity_id else None,
        }),
        tags=["context", "reports", "artifacts"],
        ttl_s=DEFAULT_BIG_CACHE_TTL_S,
        response_model=ComposedContextResponse,
        builder=lambda: _page_context_reports_build(
            pool, redis,
            profile_id=profile_id,
            entity_id=entity_id,
        ),
        bypass_cache=bypass_cache,
    )


async def _page_context_reports_build(
    pool: asyncpg.Pool,
    redis: Redis,
    *,
    profile_id: UUID,
    entity_id: UUID | None = None,
) -> ComposedContextResponse:
    """Reports page context.

    Flow:
      1. resolve_profile_identity_context -> profile identity (kept, not discarded)
      2. Evaluate caller permissions using profile data
      3. Assemble ComposedContextResponse
    """
    from fastapi import HTTPException

    # -- Step 1: Profile context ------------------------------------------------

    profile = await resolve_profile_identity_context(pool, profile_id, redis)

    if profile is None:
        raise HTTPException(
            status_code=401,
            detail="Profile not found. Please sign in again.",
        )

    # -- Step 2: Page metadata --------------------------------------------------

    page_metadata = compute_docs_metadata(_PAGE_METADATA)

    # -- Step 3: Evaluate caller permissions ------------------------------------
    # Reports has no artifact-level permissions module; use simple role defaults.

    caller_permissions = CallerPermissions(
        can_create=False,
        can_draft=False,
        can_duplicate=False,
    )

    # -- Step 4: Build profile summary ------------------------------------------

    profile_summary = await build_profile_summary(pool, redis, profile)

    # -- Step 5: Starter prompts --------------------------------------------------

    prompts = OperationPrompts(prompts={
        "search": [
            StarterPrompt(title="Generate report", content="Search and generate a comprehensive performance report with overview and trends."),
            StarterPrompt(title="Analyze trends", content="Search report data to identify performance trends over time."),
            StarterPrompt(title="Compare cohorts", content="Search reports to compare performance metrics across cohorts."),
        ],
        "export": [
            StarterPrompt(title="Export reports", content="Export report analytics with overview and trend data as CSV."),
            StarterPrompt(title="Download analysis", content="Generate a downloadable comprehensive performance analysis report."),
        ],
        "refresh": [
            StarterPrompt(title="Refresh reports", content="Refresh reports materialized views with the latest analytics data."),
            StarterPrompt(title="Rebuild sections", content="Rebuild report sections including overview, leaderboard, and trends."),
        ],
    })

    # -- Step 6: Assemble response ----------------------------------------------

    # Lazy imports to avoid circular dependencies
    from app.infra.reports.permissions import (
        build_reports_sections,
        compute_history_section,
        compute_leaderboard_section,
        compute_overview_section,
        compute_reports_header_metrics,
        compute_trends_section,
    )
    from app.routes.attempt.report.export import export_reports
    from app.routes.attempt.report.refresh import reports_refresh
    from app.routes.attempt.report.search import get_reports

    return ComposedContextResponse(
        name="reports",
        type="analytics",
        description=(
            "Reports analytics generates comprehensive performance reports "
            "with overview metrics, leaderboard rankings, trend analysis, "
            "and historical tracking."
        ),
        entries=[],
        resources=[],
        permission_docs=[
            get_operation_info(
                compute_reports_header_metrics,
                description="Compute header-level aggregated metrics for reports.",
            ),
            get_operation_info(
                compute_overview_section,
                description="Compute the overview section with summary metrics.",
            ),
            get_operation_info(
                compute_leaderboard_section,
                description="Compute the leaderboard section with rankings.",
            ),
            get_operation_info(
                compute_trends_section,
                description="Compute the trends section with time-series analysis.",
            ),
            get_operation_info(
                compute_history_section,
                description="Compute the history section with historical records.",
            ),
            get_operation_info(
                build_reports_sections,
                description="Build the complete reports bundle with all sections.",
            ),
        ],
        api_operations=[
            get_operation_info(
                get_reports,
                description="POST /search — Search and generate report analytics.",
            ),
            get_operation_info(
                reports_refresh,
                description="POST /refresh — Refresh reports materialized views.",
            ),
            get_operation_info(
                export_reports,
                description="POST /export — Export reports data as CSV/ZIP.",
            ),
        ],
        page_metadata=page_metadata,
        prompts=prompts,
        profile=profile_summary,
        caller_permissions=caller_permissions,
    )
