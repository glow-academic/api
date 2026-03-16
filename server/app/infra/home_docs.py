"""Home docs logic — composable infra architecture.

Composes existing black-box tool docs:
  1. resolve_profile_identity_context — profile (role, departments)
  2. Entry tool docs — home entry tables, MV, connections, operations
  3. Permission functions — introspected via get_operation_info
  4. API operations — all public route handlers introspected
"""

from __future__ import annotations

import asyncio
from uuid import UUID

import asyncpg
from redis.asyncio import Redis

from app.infra.docs.get_operation_info import get_operation_info
from app.infra.docs.types import ComposedDocsResponse, DocsResponse
from app.infra.docs_helper import PageMetadataConfig, compute_docs_metadata
from app.infra.profile_identity_context import resolve_profile_identity_context

# Entry tool docs
from app.tools.entries.home.docs import get_home_docs

_PAGE_METADATA = PageMetadataConfig(
    list_title="Home",
    list_description="View personalized simulation dashboard.",
    detail_title="Home",
    detail_description="View personal stats and progress tracking.",
    new_title="Home",
    new_description="View personalized simulation dashboard.",
)


async def docs_home_client(
    pool: asyncpg.Pool,
    redis: Redis,
    *,
    profile_id: UUID,
    entity_id: UUID | None = None,
) -> ComposedDocsResponse:
    """Home docs using composable infra functions.

    Flow:
      1. resolve_profile_identity_context -> profile check
      2. Parallel: entry docs
      3. Assemble ComposedDocsResponse with permissions + API operations
    """
    from fastapi import HTTPException

    # -- Step 1: Profile context ------------------------------------------

    profile = await resolve_profile_identity_context(pool, profile_id, redis)

    if profile is None:
        raise HTTPException(
            status_code=401,
            detail="Profile not found. Please sign in again.",
        )

    # -- Step 2: Parallel docs fetches ------------------------------------

    async def _fetch_home_docs() -> DocsResponse:
        async with pool.acquire() as conn:
            return await get_home_docs(conn)

    (home,) = await asyncio.gather(
        _fetch_home_docs(),
    )

    # -- Page metadata -----------------------------------------------------

    page_metadata = compute_docs_metadata(_PAGE_METADATA)

    # -- Step 3: Assemble response ----------------------------------------

    # Lazy imports to avoid circular dependencies
    from app.infra.home_permissions import (
        compute_completion_pct,
        compute_mode,
        compute_pass_pct,
        compute_score_status,
        compute_show_continue,
        compute_show_view,
        compute_status,
        compute_status_instructional,
        format_cohort_names,
    )
    from app.routes.v5.home.export import export_home
    from app.routes.v5.home.get import home_get
    from app.routes.v5.home.search import search_home

    return ComposedDocsResponse(
        name="home",
        type="analytics",
        description=(
            "Home analytics provides personalized dashboard views with "
            "simulation history, completion stats, and progress tracking."
        ),
        entries=[home],
        resources=[],
        permissions=[
            get_operation_info(
                compute_completion_pct,
                description="Compute completion percentage for a simulation.",
            ),
            get_operation_info(
                compute_mode,
                description="Compute the display mode for an attempt.",
            ),
            get_operation_info(
                compute_pass_pct,
                description="Compute pass percentage for a simulation.",
            ),
            get_operation_info(
                compute_score_status,
                description="Compute score status label for display.",
            ),
            get_operation_info(
                compute_show_continue,
                description="Determine whether to show the continue button.",
            ),
            get_operation_info(
                compute_show_view,
                description="Determine whether to show the view button.",
            ),
            get_operation_info(
                compute_status,
                description="Compute status label for a simulation attempt.",
            ),
            get_operation_info(
                compute_status_instructional,
                description="Compute instructional status label for a simulation attempt.",
            ),
            get_operation_info(
                format_cohort_names,
                description="Format cohort names for display.",
            ),
        ],
        api_operations=[
            get_operation_info(
                home_get,
                description="POST /get — Get home dashboard with personal stats.",
            ),
            get_operation_info(
                search_home,
                description="POST /search — Search home history entries.",
            ),
            get_operation_info(
                export_home,
                description="POST /export — Export home data as CSV/ZIP.",
            ),
        ],
        page_metadata=page_metadata,
    )
