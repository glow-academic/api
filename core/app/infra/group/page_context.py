"""Group page context — docs + profile identity + evaluated permissions.

Superset of docs.py. A single endpoint that gives the client everything
it needs to render the group page:
  1. resolve_profile_identity_context — who you are (name, role, departments)
  2. Entry docs — groups entry tables, MV, operations (same as docs.py)
  3. Page metadata — titles and descriptions for list/detail/new views
  4. Profile summary + caller permissions (no entity-level perms for analytics)
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
    DocsResponse,
)
from app.infra.docs.build_profile_summary import build_profile_summary
from app.infra.docs_helper import PageMetadataConfig, compute_docs_metadata
from app.infra.profile_identity_context import resolve_profile_identity_context

# Entry tool docs
from app.tools.entries.groups.docs import get_groups_docs

_PAGE_METADATA = PageMetadataConfig(
    list_title="Groups",
    list_description="View test invocation group results.",
    detail_title="Group",
    detail_description="View group runs and aggregated metrics.",
    new_title="Group",
    new_description="View test invocation group results.",
)


async def page_context_group_impl(
    pool: asyncpg.Pool,
    redis: Redis,
    *,
    profile_id: UUID,
    entity_id: UUID | None = None,
    **_kwargs,
) -> ComposedContextResponse:
    """Group page context — superset of docs_group_impl.

    Flow:
      1. resolve_profile_identity_context -> profile identity (kept, not discarded)
      2. Parallel: entry docs
      3. Assemble ComposedContextResponse with profile + permissions
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

    async def _fetch_groups_docs() -> DocsResponse:
        async with pool.acquire() as conn:
            return await get_groups_docs(conn)

    (groups,) = await asyncio.gather(
        _fetch_groups_docs(),
    )

    # -- Step 3: Page metadata --------------------------------------------------

    page_metadata = compute_docs_metadata(_PAGE_METADATA)

    # -- Step 4: Caller permissions (analytics — no entity-level perms) ---------

    caller_permissions = CallerPermissions(
        can_create=False,
        can_draft=False,
        can_duplicate=False,
    )

    # -- Step 5: Build profile summary ------------------------------------------

    profile_summary = await build_profile_summary(pool, redis, profile)

    # -- Step 6: Assemble response ----------------------------------------------

    # Lazy imports to avoid circular dependencies
    from app.routes.group.export import export_group
    from app.routes.group.get import get_group

    return ComposedContextResponse(
        name="group",
        type="analytics",
        description=(
            "Group analytics provides detailed views of test invocation groups "
            "including runs, results, and aggregated metrics."
        ),
        entries=[groups],
        resources=[],
        permission_docs=[],
        api_operations=[
            get_operation_info(
                get_group,
                description="POST /get — Get a single group with runs and metrics.",
            ),
            get_operation_info(
                export_group,
                description="POST /export — Export group data as CSV/ZIP.",
            ),
        ],
        page_metadata=page_metadata,
        profile=profile_summary,
        caller_permissions=caller_permissions,
    )
