"""Home page context — docs + profile identity + evaluated permissions.

Superset of docs.py. A single endpoint that gives the client everything
it needs to render the home page:
  1. resolve_profile_identity_context — who you are (name, role, departments)
  2. Entry tool docs — home entry tables, MV, connections, operations
  3. Permission evaluation — concrete booleans for THIS caller
  4. API operations — all public route handlers introspected
  5. Page metadata — titles and descriptions for list/detail/new views
"""

from __future__ import annotations

import asyncio
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


async def page_context_home_impl(
    pool: asyncpg.Pool,
    redis: Redis,
    *,
    profile_id: UUID,
    entity_id: UUID | None = None,
    **_kwargs,
) -> ComposedContextResponse:
    """Home page context.

    Flow:
      1. resolve_profile_identity_context -> profile identity (kept, not discarded)
      2. Parallel: entry docs
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

    async def _fetch_home_docs() -> object:
        async with pool.acquire() as conn:
            return await get_home_docs(conn)

    (home,) = await asyncio.gather(
        _fetch_home_docs(),
    )

    # -- Step 3: Page metadata --------------------------------------------------

    page_metadata = compute_docs_metadata(_PAGE_METADATA)

    # -- Step 4: Evaluate caller permissions ------------------------------------
    # Home is analytics — no entity-level create/draft/duplicate.
    # CallerPermissions still populated for sidebar/nav consistency.

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
            StarterPrompt(title="View progress", content="Show my personal simulation stats, completion history, and progress."),
            StarterPrompt(title="Check next steps", content="Identify my next assigned simulations and upcoming deadlines."),
            StarterPrompt(title="Review scores", content="Summarize my recent scores and highlight areas for improvement."),
        ],
        "search": [
            StarterPrompt(title="Find simulations", content="Search my simulation history by scenario name or completion status."),
            StarterPrompt(title="Filter by date", content="Search my home dashboard entries filtered by date range."),
        ],
        "export": [
            StarterPrompt(title="Export progress", content="Export my personal dashboard data and completion history as CSV."),
            StarterPrompt(title="Download stats", content="Generate a downloadable report of my simulation performance."),
        ],
        "refresh": [
            StarterPrompt(title="Refresh home", content="Refresh home materialized views to show the latest activity."),
            StarterPrompt(title="Update stats", content="Rebuild my personal dashboard metrics with the most recent data."),
        ],
    })

    # -- Step 7: Assemble response ----------------------------------------------

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
    from app.routes.attempt.home.export import export_home
    from app.routes.attempt.home.get import home_get
    from app.routes.attempt.home.refresh import home_refresh
    from app.routes.attempt.home.search import search_home

    return ComposedContextResponse(
        name="home",
        type="analytics",
        description=(
            "Home analytics provides personalized dashboard views with "
            "simulation history, completion stats, and progress tracking."
        ),
        artifact=None,
        entries=[home],
        resources=[],
        permission_docs=[
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
                home_refresh,
                description="POST /refresh — Refresh home materialized views.",
            ),
            get_operation_info(
                export_home,
                description="POST /export — Export home data as CSV/ZIP.",
            ),
        ],
        page_metadata=page_metadata,
        prompts=prompts,
        profile=profile_summary,
        caller_permissions=caller_permissions,
    )
