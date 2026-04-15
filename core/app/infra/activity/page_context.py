"""Activity page context — docs + profile identity + evaluated permissions.

Superset of docs.py. A single endpoint that gives the client everything
it needs to render the activity page:
  1. resolve_profile_identity_context — who you are (name, role, departments)
  2. Entry docs — activity entry schema introspection (same as docs.py)
  3. Permission evaluation — concrete booleans for THIS caller
  4. Page metadata — titles and descriptions for list/detail/new views
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
)
from app.infra.docs.build_profile_summary import build_profile_summary
from app.infra.docs_helper import PageMetadataConfig, compute_docs_metadata
from app.infra.profile_identity_context import resolve_profile_identity_context

# Entry tool docs
from app.tools.entries.activity.docs import get_activity_docs

_PAGE_METADATA = PageMetadataConfig(
    list_title="Activity",
    list_description="Track user engagement and usage metrics.",
    detail_title="Activity",
    detail_description="View activity analytics for a profile.",
    new_title="Activity",
    new_description="Track user engagement and usage metrics.",
)


async def page_context_activity_impl(
    pool: asyncpg.Pool,
    redis: Redis,
    *,
    profile_id: UUID,
    entity_id: UUID | None = None,
    **_kwargs,
) -> ComposedContextResponse:
    """Activity page context — superset of docs_activity_impl.

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

    async def _fetch_activity_docs() -> object:
        async with pool.acquire() as c:
            return await get_activity_docs(c)

    (activity_entry,) = await asyncio.gather(
        _fetch_activity_docs(),
    )

    # -- Step 3: Page metadata --------------------------------------------------

    page_metadata = compute_docs_metadata(_PAGE_METADATA)

    # -- Step 4: Evaluate caller permissions ------------------------------------
    # Activity has no artifact-level permissions module; use simple role defaults.

    caller_permissions = CallerPermissions(
        can_create=False,
        can_draft=False,
        can_duplicate=False,
    )

    # -- Step 5: Build profile summary ------------------------------------------

    profile_summary = await build_profile_summary(pool, redis, profile)

    # -- Step 6: Assemble response ----------------------------------------------

    # Lazy imports to avoid circular dependencies
    from app.routes.activity.export import export_activity
    from app.routes.activity.get import get_activity
    from app.routes.activity.problem import create_problem
    from app.routes.activity.refresh import activity_refresh
    from app.routes.activity.resolve import resolve_problem
    from app.routes.activity.search import search_activity

    return ComposedContextResponse(
        name="activity",
        type="analytics",
        description=(
            "Activity analytics tracks user engagement, login patterns, "
            "problem flags, and usage metrics across the platform."
        ),
        entries=[activity_entry],
        resources=[],
        permission_docs=[],
        api_operations=[
            get_operation_info(
                get_activity,
                description="POST /get — Get activity analytics for a profile.",
            ),
            get_operation_info(
                search_activity,
                description="POST /search — Search activity history with filters.",
            ),
            get_operation_info(
                resolve_problem,
                description="POST /resolve — Resolve a flagged problem.",
            ),
            get_operation_info(
                create_problem,
                description="POST /problem — Create a new problem flag.",
            ),
            get_operation_info(
                activity_refresh,
                description="POST /refresh — Refresh activity materialized views.",
            ),
            get_operation_info(
                export_activity,
                description="POST /export — Export activity data as CSV/ZIP.",
            ),
        ],
        page_metadata=page_metadata,
        profile=profile_summary,
        caller_permissions=caller_permissions,
    )
