"""Benchmark page context — docs + profile identity + evaluated permissions.

Superset of docs.py. A single endpoint that gives the client everything
it needs to render the benchmark page:
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
from app.infra.server_timing import timed
from app.tools.entries.benchmark.docs import get_benchmark_docs
from app.utils.cache.big import (
    DEFAULT_BIG_CACHE_TTL_S,
    big_cache_key,
    get_or_build,
)

_PAGE_METADATA = PageMetadataConfig(
    list_title="Benchmarks",
    list_description="Evaluate AI model performance across test scenarios.",
    detail_title="Benchmark",
    detail_description="View benchmark evaluation results and history.",
    new_title="Benchmark",
    new_description="Evaluate AI model performance across test scenarios.",
)


async def page_context_benchmark_impl(
    pool: asyncpg.Pool,
    redis: Redis,
    *,
    profile_id: UUID,
    entity_id: UUID | None = None,
    schema: bool = False,
    bypass_cache: bool = False,
    **_kwargs,
) -> ComposedContextResponse:
    """benchmark page context — big-cache wrapped."""
    return await get_or_build(
        redis=redis,
        key=big_cache_key("benchmark/page_context", {
            "profile_id": str(profile_id),
            "entity_id": str(entity_id) if entity_id else None,
            "schema": schema,
        }),
        tags=["context", "benchmark", "artifacts"],
        ttl_s=DEFAULT_BIG_CACHE_TTL_S,
        response_model=ComposedContextResponse,
        builder=lambda: _page_context_benchmark_build(
            pool, redis,
            profile_id=profile_id,
            entity_id=entity_id,
            schema=schema,
        ),
        bypass_cache=bypass_cache,
    )


async def _page_context_benchmark_build(
    pool: asyncpg.Pool,
    redis: Redis,
    *,
    profile_id: UUID,
    entity_id: UUID | None = None,
    schema: bool = False,
) -> ComposedContextResponse:
    """Benchmark page context.

    Flow:
      1. resolve_profile_identity_context -> profile identity (kept, not discarded)
      2. Parallel: entry docs fetch
      3. Evaluate caller permissions using profile data
      4. Assemble ComposedContextResponse
    """
    from fastapi import HTTPException

    # -- Step 1: Profile context ------------------------------------------------

    with timed("profile"):
        profile = await resolve_profile_identity_context(pool, profile_id, redis)

    if profile is None:
        raise HTTPException(
            status_code=401,
            detail="Profile not found. Please sign in again.",
        )

    # -- Step 2: Parallel docs fetches ------------------------------------------

    async def _get_benchmark_docs() -> object:
        if not schema:
            return None  # type: ignore[return-value]
        async with pool.acquire() as conn:
            return await get_benchmark_docs(conn)

    with timed("docs_gather"):
     (benchmark_entry,) = await asyncio.gather(
        _get_benchmark_docs(),
    )

    # -- Step 3: Page metadata --------------------------------------------------

    page_metadata = compute_docs_metadata(_PAGE_METADATA)

    # -- Step 4: Evaluate caller permissions ------------------------------------
    # Benchmark is an analytics artifact — no create/draft/duplicate semantics.
    # Provide safe defaults for the CallerPermissions fields.

    caller_permissions = CallerPermissions(
        can_create=False,
        can_draft=False,
        can_duplicate=False,
    )

    # -- Step 5: Build profile summary ------------------------------------------

    with timed("profile_summary"):
        profile_summary = await build_profile_summary(pool, redis, profile)

    # -- Step 6: Starter prompts --------------------------------------------------

    prompts = OperationPrompts(prompts={
        "get": [
            StarterPrompt(title="View benchmark", content="Show evaluation results and model performance for this benchmark."),
            StarterPrompt(title="Compare models", content="Compare model scores and pass rates across benchmark test scenarios."),
        ],
        "search": [
            StarterPrompt(title="Find benchmarks", content="Search benchmark run history filtered by date or test configuration."),
            StarterPrompt(title="Track regressions", content="Identify performance regressions across recent benchmark runs."),
            StarterPrompt(title="Filter by status", content="Search benchmarks filtered by pass/fail status or score range."),
        ],
        "export": [
            StarterPrompt(title="Export benchmarks", content="Export benchmark evaluation data as a CSV report."),
            StarterPrompt(title="Download comparison", content="Generate a downloadable model performance comparison report."),
        ],
        "refresh": [
            StarterPrompt(title="Refresh benchmarks", content="Refresh benchmark materialized views with the latest run data."),
            StarterPrompt(title="Rebuild metrics", content="Rebuild aggregated benchmark metrics from recent test results."),
        ],
    })

    # -- Step 7: Assemble response ----------------------------------------------

    # Lazy imports to avoid circular dependencies
    from app.infra.benchmark.permissions import (
        compute_benchmark_eval_status,
    )
    from app.routes.test.benchmark.export import export_benchmark
    from app.routes.test.benchmark import get_benchmark
    from app.routes.test.benchmark.refresh import benchmark_refresh
    # /benchmark/search was promoted to top-level /test/invocations.
    from app.routes.test.invocations import list_invocations

    return ComposedContextResponse(
        name="benchmark",
        type="analytics",
        description=(
            "Benchmark analytics evaluates AI model performance across "
            "standardized test scenarios with scoring and comparison metrics."
        ),
        entries=([benchmark_entry] if schema else None),
        resources=([] if schema else None),
        permission_docs=([
            get_operation_info(
                compute_benchmark_eval_status,
                description="Compute eval card status from aggregated test invocation data.",
            ),
        ] if schema else None),
        api_operations=([
            get_operation_info(
                get_benchmark,
                description="POST /get — Get benchmark evaluation results.",
            ),
            get_operation_info(
                list_invocations,
                description="POST /test/invocations — List test invocations with pagination/filters.",
            ),
            get_operation_info(
                benchmark_refresh,
                description="POST /refresh — Refresh benchmark materialized views.",
            ),
            get_operation_info(
                export_benchmark,
                description="POST /export — Export benchmark data as CSV/ZIP.",
            ),
        ] if schema else None),
        page_metadata=page_metadata,
        prompts=prompts,
        profile=profile_summary,
        caller_permissions=caller_permissions,
    )
