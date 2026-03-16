"""Dashboard docs logic — composable infra architecture.

Composes existing black-box tool docs:
  1. resolve_profile_identity_context — profile (role, departments)
  2. Permission functions — introspected via get_operation_info
  3. API operations — all public route handlers introspected
"""

from __future__ import annotations

from uuid import UUID

import asyncpg
from redis.asyncio import Redis

from app.infra.docs.get_operation_info import get_operation_info
from app.infra.docs.types import ComposedDocsResponse
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


async def docs_dashboard_impl(
    pool: asyncpg.Pool,
    redis: Redis,
    *,
    profile_id: UUID,
    entity_id: UUID | None = None,
) -> ComposedDocsResponse:
    """Dashboard docs using composable infra functions.

    Flow:
      1. resolve_profile_identity_context -> profile check
      2. Assemble ComposedDocsResponse with permissions + API operations
    """
    from fastapi import HTTPException

    # -- Step 1: Profile context ------------------------------------------

    profile = await resolve_profile_identity_context(pool, profile_id, redis)

    if profile is None:
        raise HTTPException(
            status_code=401,
            detail="Profile not found. Please sign in again.",
        )

    # -- Page metadata -----------------------------------------------------

    page_metadata = compute_docs_metadata(_PAGE_METADATA)

    # -- Step 2: Assemble response ----------------------------------------

    # Lazy imports to avoid circular dependencies
    from app.infra.dashboard.permissions import (
        build_dashboard_bundle,
        compute_footer_metrics,
        compute_header_metrics,
        compute_primary_metrics,
        compute_secondary_metrics,
    )
    from app.routes.v5.dashboard.export import export_dashboard
    from app.routes.v5.dashboard.get import get_dashboard
    from app.routes.v5.dashboard.refresh import dashboard_refresh
    from app.routes.v5.dashboard.search import search_dashboard

    return ComposedDocsResponse(
        name="dashboard",
        type="analytics",
        description=(
            "Dashboard analytics provides aggregated performance metrics, "
            "trend analysis, and summary sections across simulations and cohorts."
        ),
        entries=[],
        resources=[],
        permissions=[
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
    )
