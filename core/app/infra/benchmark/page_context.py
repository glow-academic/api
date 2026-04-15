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

from app.infra.docs.get_operation_info import get_operation_info
from app.infra.docs.types import (
    CallerPermissions,
    ComposedContextResponse,
)
from app.infra.docs.build_profile_summary import build_profile_summary
from app.infra.docs_helper import PageMetadataConfig, compute_docs_metadata
from app.infra.profile_identity_context import resolve_profile_identity_context
from app.tools.entries.benchmark.docs import get_benchmark_docs

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
    **_kwargs,
) -> ComposedContextResponse:
    """Benchmark page context — superset of docs_benchmark_impl.

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

    async def _get_benchmark_docs() -> object:
        async with pool.acquire() as conn:
            return await get_benchmark_docs(conn)

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

    profile_summary = await build_profile_summary(pool, redis, profile)

    # -- Step 6: Assemble response ----------------------------------------------

    # Lazy imports to avoid circular dependencies
    from app.infra.benchmark.permissions import (
        compute_benchmark_eval_status,
    )
    from app.routes.benchmark.export import export_benchmark
    from app.routes.benchmark.get import get_benchmark
    from app.routes.benchmark.refresh import benchmark_refresh
    from app.routes.benchmark.search import search_benchmark_history

    return ComposedContextResponse(
        name="benchmark",
        type="analytics",
        description=(
            "Benchmark analytics evaluates AI model performance across "
            "standardized test scenarios with scoring and comparison metrics."
        ),
        entries=[benchmark_entry],
        resources=[],
        permission_docs=[
            get_operation_info(
                compute_benchmark_eval_status,
                description="Compute eval card status from aggregated test invocation data.",
            ),
        ],
        api_operations=[
            get_operation_info(
                get_benchmark,
                description="POST /get — Get benchmark evaluation results.",
            ),
            get_operation_info(
                search_benchmark_history,
                description="POST /search — Search benchmark run history.",
            ),
            get_operation_info(
                benchmark_refresh,
                description="POST /refresh — Refresh benchmark materialized views.",
            ),
            get_operation_info(
                export_benchmark,
                description="POST /export — Export benchmark data as CSV/ZIP.",
            ),
        ],
        page_metadata=page_metadata,
        profile=profile_summary,
        caller_permissions=caller_permissions,
    )
