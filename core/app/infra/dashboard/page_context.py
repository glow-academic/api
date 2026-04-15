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

from app.infra.docs.get_operation_info import get_operation_info
from app.infra.docs.types import (
    CallerPermissions,
    ComposedContextResponse,
)
from app.infra.docs.build_profile_summary import build_profile_summary
from app.infra.docs_helper import PageMetadataConfig, compute_docs_metadata
from app.infra.profile_identity_context import resolve_profile_identity_context

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
    **_kwargs,
) -> ComposedContextResponse:
    """Dashboard page context — superset of docs_dashboard_impl.

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
    # Dashboard is analytics — no entity-level create/draft/duplicate.
    # CallerPermissions still populated for sidebar/nav consistency.

    caller_permissions = CallerPermissions(
        can_create=False,
        can_draft=False,
        can_duplicate=False,
    )

    # -- Step 4: Build profile summary ------------------------------------------

    profile_summary = await build_profile_summary(pool, redis, profile)

    # -- Step 5: Assemble response ----------------------------------------------

    # Lazy imports to avoid circular dependencies
    from app.infra.dashboard.permissions import (
        build_dashboard_bundle,
        compute_footer_metrics,
        compute_header_metrics,
        compute_primary_metrics,
        compute_secondary_metrics,
    )
    from app.routes.dashboard.export import export_dashboard
    from app.routes.dashboard.get import get_dashboard
    from app.routes.dashboard.refresh import dashboard_refresh
    from app.routes.dashboard.search import search_dashboard

    return ComposedContextResponse(
        name="dashboard",
        type="analytics",
        description=(
            "Dashboard analytics provides aggregated performance metrics, "
            "trend analysis, and summary sections across simulations and cohorts."
        ),
        artifact=None,
        entries=[],
        resources=[],
        permission_docs=[
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
        ],
        api_operations=[
            get_operation_info(
                get_dashboard,
                description="POST /get — Get dashboard analytics with metrics and sections.",
            ),
            get_operation_info(
                search_dashboard,
                description="POST /search — Search dashboard history entries.",
            ),
            get_operation_info(
                dashboard_refresh,
                description="POST /refresh — Refresh dashboard materialized views.",
            ),
            get_operation_info(
                export_dashboard,
                description="POST /export — Export dashboard data as CSV/ZIP.",
            ),
        ],
        page_metadata=page_metadata,
        profile=profile_summary,
        caller_permissions=caller_permissions,
    )
