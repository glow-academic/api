"""Leaderboard page context — docs + profile identity + evaluated permissions.

Superset of docs.py. A single endpoint that gives the client everything
it needs to render the leaderboard page:
  1. resolve_profile_identity_context — who you are (name, role, departments)
  2. Permission evaluation — concrete booleans for THIS caller
  3. Page metadata — titles and descriptions for list/detail/new views
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
    list_title="Leaderboard",
    list_description="View performance rankings and accolades.",
    detail_title="Leaderboard",
    detail_description="View leaderboard rankings and comparative metrics.",
    new_title="Leaderboard",
    new_description="View leaderboard rankings and comparative metrics.",
)


async def page_context_leaderboard_impl(
    pool: asyncpg.Pool,
    redis: Redis,
    *,
    profile_id: UUID,
    entity_id: UUID | None = None,
    bypass_cache: bool = False,
    **_kwargs,
) -> ComposedContextResponse:
    """leaderboard page context — big-cache wrapped."""
    return await get_or_build(
        redis=redis,
        key=big_cache_key("leaderboard/page_context", {
            "profile_id": str(profile_id),
            "entity_id": str(entity_id) if entity_id else None,
        }),
        tags=["context", "leaderboard", "artifacts"],
        ttl_s=DEFAULT_BIG_CACHE_TTL_S,
        response_model=ComposedContextResponse,
        builder=lambda: _page_context_leaderboard_build(
            pool, redis,
            profile_id=profile_id,
            entity_id=entity_id,
        ),
        bypass_cache=bypass_cache,
    )


async def _page_context_leaderboard_build(
    pool: asyncpg.Pool,
    redis: Redis,
    *,
    profile_id: UUID,
    entity_id: UUID | None = None,
) -> ComposedContextResponse:
    """Leaderboard page context.

    Flow:
      1. resolve_profile_identity_context -> profile identity (kept, not discarded)
      2. Evaluate caller permissions using profile data
      3. Assemble ComposedContextResponse with permissions + API operations
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
    # Leaderboard is an analytics view — no create/duplicate/draft gates.

    caller_permissions = CallerPermissions(
        can_create=False,
        can_draft=False,
        can_duplicate=False,
    )

    # -- Step 4: Build profile summary ------------------------------------------

    profile_summary = await build_profile_summary(pool, redis, profile)

    # -- Step 5: Starter prompts --------------------------------------------------

    prompts = OperationPrompts(prompts={
        "get": [
            StarterPrompt(title="View rankings", content="Show current leaderboard standings with scores and accolades."),
            StarterPrompt(title="Identify leaders", content="Highlight top performers and their winning metrics."),
            StarterPrompt(title="Check standing", content="Show where a specific user ranks on the leaderboard."),
        ],
        "search": [
            StarterPrompt(title="Compare periods", content="Search leaderboard history to compare rankings across time periods."),
            StarterPrompt(title="Filter by cohort", content="Search leaderboard entries filtered by cohort or department."),
        ],
        "export": [
            StarterPrompt(title="Export rankings", content="Export leaderboard rankings and accolade data as CSV."),
            StarterPrompt(title="Download standings", content="Generate a downloadable leaderboard standings report."),
        ],
        "refresh": [
            StarterPrompt(title="Refresh rankings", content="Refresh leaderboard materialized views with the latest scores."),
            StarterPrompt(title="Update standings", content="Rebuild leaderboard rankings to reflect recent simulation results."),
        ],
    })

    # -- Step 6: Assemble response ----------------------------------------------

    # Lazy imports to avoid circular dependencies
    from app.infra.leaderboard.permissions import (
        build_leaderboard_rows,
        build_leaderboard_sections,
        compute_accolade_winners,
        compute_message_stats,
    )
    from app.routes.attempt.leaderboard.export import export_leaderboard
    from app.routes.attempt.leaderboard.get import get_leaderboard
    from app.routes.attempt.leaderboard.refresh import leaderboard_refresh
    from app.routes.attempt.leaderboard.search import search_leaderboard

    return ComposedContextResponse(
        name="leaderboard",
        type="analytics",
        description=(
            "Leaderboard analytics ranks user performance with accolades, "
            "comparative metrics, and historical tracking across simulations."
        ),
        entries=[],
        resources=[],
        permission_docs=[
            get_operation_info(
                build_leaderboard_rows,
                description="Build ranked leaderboard data rows from MV slices.",
            ),
            get_operation_info(
                compute_accolade_winners,
                description="Compute accolade winners from leaderboard data rows.",
            ),
            get_operation_info(
                build_leaderboard_sections,
                description="Build leaderboard sections with status and metrics.",
            ),
            get_operation_info(
                compute_message_stats,
                description="Compute message-level statistics for leaderboard entries.",
            ),
        ],
        api_operations=[
            get_operation_info(
                get_leaderboard,
                description="POST /get — Get leaderboard rankings and accolades.",
            ),
            get_operation_info(
                search_leaderboard,
                description="POST /search — Search leaderboard history entries.",
            ),
            get_operation_info(
                leaderboard_refresh,
                description="POST /refresh — Refresh leaderboard materialized views.",
            ),
            get_operation_info(
                export_leaderboard,
                description="POST /export — Export leaderboard data as CSV/ZIP.",
            ),
        ],
        page_metadata=page_metadata,
        prompts=prompts,
        profile=profile_summary,
        caller_permissions=caller_permissions,
    )
