"""Reports docs logic — composable infra architecture.

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
    list_title="Reports",
    list_description="Generate comprehensive performance reports.",
    detail_title="Reports",
    detail_description="View report analytics with overview and trends.",
    new_title="Reports",
    new_description="View report analytics with overview and trends.",
)


async def docs_reports_impl(
    pool: asyncpg.Pool,
    redis: Redis,
    *,
    profile_id: UUID,
    entity_id: UUID | None = None,
) -> ComposedDocsResponse:
    """Reports docs using composable infra functions.

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

    # ── Page metadata ───────────────────────────────────────────────────
    page_metadata = compute_docs_metadata(_PAGE_METADATA)

    # -- Step 2: Assemble response ----------------------------------------

    # Lazy imports to avoid circular dependencies
    from app.infra.reports.permissions import (
        build_reports_sections,
        compute_history_section,
        compute_leaderboard_section,
        compute_overview_section,
        compute_reports_header_metrics,
        compute_trends_section,
    )
    from app.routes.v5.reports.export import export_reports
    from app.routes.v5.reports.refresh import reports_refresh
    from app.routes.v5.reports.search import get_reports

    return ComposedDocsResponse(
        name="reports",
        type="analytics",
        description=(
            "Reports analytics generates comprehensive performance reports "
            "with overview metrics, leaderboard rankings, trend analysis, "
            "and historical tracking."
        ),
        entries=[],
        resources=[],
        permissions=[
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
    )
