"""Invocation page context — docs + profile identity + evaluated permissions.

Superset of docs.py. A single endpoint that gives the client everything
it needs to render the invocation page:
  1. resolve_profile_identity_context — who you are (name, role, departments)
  2. Entry docs — schema introspection (same as docs.py)
  3. Permission evaluation — concrete booleans for THIS caller
  4. Page metadata — titles and descriptions for list/detail/new views
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
    OperationPrompts,
    StarterPrompt,
)
from app.infra.docs_helper import PageMetadataConfig, compute_docs_metadata
from app.infra.profile_identity_context import resolve_profile_identity_context

# Entry tool docs
from app.tools.entries.invocation.docs import get_invocation_docs
from app.utils.cache.big import (
    DEFAULT_BIG_CACHE_TTL_S,
    big_cache_key,
    get_or_build,
)

_PAGE_METADATA = PageMetadataConfig(
    list_title="Invocations",
    list_description="View test invocation results and drafts.",
    detail_title="Invocation",
    detail_description="View invocation execution details and run history.",
    new_title="Invocation",
    new_description="View invocation execution details and run history.",
)


async def page_context_invocation_impl(
    pool: asyncpg.Pool,
    redis: Redis,
    *,
    profile_id: UUID,
    entity_id: UUID | None = None,
    bypass_cache: bool = False,
    **_kwargs,
) -> ComposedContextResponse:
    """invocation page context — big-cache wrapped."""
    return await get_or_build(
        redis=redis,
        key=big_cache_key("invocation/page_context", {
            "profile_id": str(profile_id),
            "entity_id": str(entity_id) if entity_id else None,
        }),
        tags=["context", "invocation", "artifacts"],
        ttl_s=DEFAULT_BIG_CACHE_TTL_S,
        response_model=ComposedContextResponse,
        builder=lambda: _page_context_invocation_build(
            pool, redis,
            profile_id=profile_id,
            entity_id=entity_id,
        ),
        bypass_cache=bypass_cache,
    )


async def _page_context_invocation_build(
    pool: asyncpg.Pool,
    redis: Redis,
    *,
    profile_id: UUID,
    entity_id: UUID | None = None,
) -> ComposedContextResponse:
    """Invocation page context.

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

    async def _get_invocation_docs() -> object:
        async with pool.acquire() as conn:
            return await get_invocation_docs(conn)

    (invocation,) = await asyncio.gather(
        _get_invocation_docs(),
    )

    # -- Step 3: Page metadata --------------------------------------------------

    page_metadata = compute_docs_metadata(_PAGE_METADATA)

    # -- Step 4: Evaluate caller permissions ------------------------------------
    # Invocation is an analytics view — no create/duplicate/draft gates.

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
            StarterPrompt(title="View invocation", content="Show execution details, run history, and results for this test invocation."),
            StarterPrompt(title="Analyze results", content="Break down pass/fail outcomes and scoring for this invocation's runs."),
            StarterPrompt(title="Review output", content="Review and explain the detailed output from this invocation."),
        ],
        "export": [
            StarterPrompt(title="Export invocation", content="Export this invocation's execution data and results as CSV."),
            StarterPrompt(title="Download history", content="Generate a downloadable report of this invocation's run history."),
        ],
    })

    # -- Step 7: Assemble response ----------------------------------------------

    # Lazy imports to avoid circular dependencies
    from app.routes.test.invocation.draft import patch_invocation_draft
    from app.routes.test.invocation.export import export_invocation
    from app.routes.test.invocation.get import invocation_get

    return ComposedContextResponse(
        name="invocation",
        type="analytics",
        description=(
            "Invocation analytics provides detailed views of test invocations "
            "including execution results, drafts, and run history."
        ),
        entries=[invocation],
        resources=[],
        permission_docs=[],
        api_operations=[
            get_operation_info(
                invocation_get,
                description="POST /get — Get a single invocation with full detail.",
            ),
            get_operation_info(
                patch_invocation_draft,
                description="PATCH /draft — Create or patch an invocation draft.",
            ),
            get_operation_info(
                export_invocation,
                description="POST /export — Export invocation data as CSV.",
            ),
        ],
        page_metadata=page_metadata,
        prompts=prompts,
        profile=profile_summary,
        caller_permissions=caller_permissions,
    )
