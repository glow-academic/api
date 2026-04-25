"""Test page context — docs + profile identity + evaluated permissions.

Superset of docs.py. A single endpoint that gives the client everything
it needs to render the test page:
  1. resolve_profile_identity_context — who you are (name, role, departments)
  2. Entry docs — test entry schema introspection (same as docs.py)
  3. Permission docs — test status computation function
  4. Permission evaluation — concrete booleans for THIS caller
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
from app.tools.entries.test.docs import get_test_docs

from app.utils.cache.big import (
    DEFAULT_BIG_CACHE_TTL_S,
    big_cache_key,
    get_or_build,
)

_PAGE_METADATA = PageMetadataConfig(
    list_title="Tests",
    list_description="View benchmark test configurations.",
    detail_title="Test",
    detail_description="View test invocations and evaluation results.",
    new_title="Test",
    new_description="View test invocations and evaluation results.",
)


async def page_context_test_impl(
    pool: asyncpg.Pool,
    redis: Redis,
    *,
    profile_id: UUID,
    entity_id: UUID | None = None,
    bypass_cache: bool = False,
    **_kwargs,
) -> ComposedContextResponse:
    """test page context — big-cache wrapped."""
    return await get_or_build(
        redis=redis,
        key=big_cache_key("test/page_context", {
            "profile_id": str(profile_id),
            "entity_id": str(entity_id) if entity_id else None,
        }),
        tags=["context", "test", "artifacts"],
        ttl_s=DEFAULT_BIG_CACHE_TTL_S,
        response_model=ComposedContextResponse,
        builder=lambda: _page_context_test_build(
            pool, redis,
            profile_id=profile_id,
            entity_id=entity_id,
        ),
        bypass_cache=bypass_cache,
    )


async def _page_context_test_build(
    pool: asyncpg.Pool,
    redis: Redis,
    *,
    profile_id: UUID,
    entity_id: UUID | None = None,
) -> ComposedContextResponse:
    """Test page context.

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

    async def _fetch_test_docs() -> object:
        async with pool.acquire() as c:
            return await get_test_docs(c)

    (test_entry,) = await asyncio.gather(
        _fetch_test_docs(),
    )

    # -- Step 3: Page metadata --------------------------------------------------

    page_metadata = compute_docs_metadata(_PAGE_METADATA)

    # -- Step 4: Evaluate caller permissions ------------------------------------
    # Test has no artifact-level permissions module; use simple role defaults.

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
            StarterPrompt(title="View test", content="Show invocations, runs, and evaluation results for this test configuration."),
            StarterPrompt(title="Analyze results", content="Break down pass/fail rates and scoring across this test's invocations."),
            StarterPrompt(title="Review failures", content="Identify failed runs and analyze root causes within this test."),
        ],
        "export": [
            StarterPrompt(title="Export test", content="Export this test's invocation data and evaluation results as CSV."),
            StarterPrompt(title="Download results", content="Generate a downloadable report of test outcomes and run history."),
        ],
    })

    # -- Step 7: Assemble response ----------------------------------------------

    # Lazy imports to avoid circular dependencies
    from app.infra.test.permissions import compute_test_status
    from app.routes.test.archive import archive_test_artifacts
    from app.routes.test.export import export_test
    from app.routes.test.get import get_test_artifact

    return ComposedContextResponse(
        name="test",
        type="analytics",
        description=(
            "Test analytics provides detailed views of benchmark test "
            "configurations including invocations, runs, and evaluation results."
        ),
        entries=[test_entry],
        resources=[],
        permission_docs=[
            get_operation_info(
                compute_test_status,
                description="Compute a minimal status label from chat completion counts.",
            ),
        ],
        api_operations=[
            get_operation_info(
                get_test_artifact,
                description="POST /get — Get a single test artifact with invocations.",
            ),
            get_operation_info(
                archive_test_artifacts,
                description="POST /archive — Archive completed tests.",
            ),
            get_operation_info(
                export_test,
                description="POST /export — Export test data as CSV/ZIP.",
            ),
        ],
        page_metadata=page_metadata,
        prompts=prompts,
        profile=profile_summary,
        caller_permissions=caller_permissions,
    )
