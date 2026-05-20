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

from app.infra.docs.build_profile_summary import build_profile_summary
from app.infra.docs.get_operation_info import get_operation_info
from app.infra.docs.types import (
    CallerPermissions,
    ComposedContextResponse,
    DocsResponse,
    OperationPrompts,
    StarterPrompt,
)
from app.infra.docs_helper import PageMetadataConfig, compute_docs_metadata
from app.infra.profile_identity_context import resolve_profile_identity_context

# Entry tool docs
from app.tools.entries.groups.docs import get_groups_docs
from app.utils.cache.big import (
    DEFAULT_BIG_CACHE_TTL_S,
    big_cache_key,
    get_or_build,
)

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
    schema: bool = False,
    bypass_cache: bool = False,
    **_kwargs,
) -> ComposedContextResponse:
    """group page context — big-cache wrapped."""
    return await get_or_build(
        redis=redis,
        key=big_cache_key("group/page_context", {
            "profile_id": str(profile_id),
            "entity_id": str(entity_id) if entity_id else None,
            "schema": schema,
        }),
        tags=["context", "group", "artifacts"],
        ttl_s=DEFAULT_BIG_CACHE_TTL_S,
        response_model=ComposedContextResponse,
        builder=lambda: _page_context_group_build(
            pool, redis,
            profile_id=profile_id,
            entity_id=entity_id,
            schema=schema,
        ),
        bypass_cache=bypass_cache,
    )


async def _page_context_group_build(
    pool: asyncpg.Pool,
    redis: Redis,
    *,
    profile_id: UUID,
    entity_id: UUID | None = None,
    schema: bool = False,
) -> ComposedContextResponse:
    """Group page context.

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
        if not schema:
            return None  # type: ignore[return-value]
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

    # -- Step 6: Starter prompts --------------------------------------------------

    prompts = OperationPrompts(prompts={
        "get": [
            StarterPrompt(title="View group", content="Show runs, results, and aggregated metrics for this test invocation group."),
            StarterPrompt(title="Analyze results", content="Break down pass rates and scoring across runs in this group."),
            StarterPrompt(title="Compare runs", content="Compare individual run results within this group."),
        ],
        "export": [
            StarterPrompt(title="Export group", content="Export this group's run data and metrics as CSV."),
            StarterPrompt(title="Download results", content="Generate a downloadable report of group performance data."),
        ],
    })

    # -- Step 7: Assemble response ----------------------------------------------

    # Lazy imports to avoid circular dependencies
    from app.routes.system.group.export import export_group
    from app.routes.system.group.get import get_group

    return ComposedContextResponse(
        name="group",
        type="analytics",
        description=(
            "Group analytics provides detailed views of test invocation groups "
            "including runs, results, and aggregated metrics."
        ),
        entries=([groups] if schema else None),
        resources=([] if schema else None),
        permission_docs=([] if schema else None),
        api_operations=([
            get_operation_info(
                get_group,
                description="POST /get — Get a single group with runs and metrics.",
            ),
            get_operation_info(
                export_group,
                description="POST /export — Export group data as CSV/ZIP.",
            ),
        ] if schema else None),
        page_metadata=page_metadata,
        prompts=prompts,
        profile=profile_summary,
        caller_permissions=caller_permissions,
    )
