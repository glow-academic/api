"""Benchmark docs logic — composable infra architecture.

Composes existing black-box tool docs:
  1. resolve_profile_identity_context — profile (role, departments)
  2. Entry tool docs — benchmark entries
  3. Permission functions — benchmark eval status
  4. API operations — all public route handlers introspected
"""

from __future__ import annotations

import asyncio
from uuid import UUID

import asyncpg
from redis.asyncio import Redis

from app.infra.docs.get_operation_info import get_operation_info
from app.infra.docs.types import ComposedDocsResponse
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


async def docs_benchmark_impl(
    pool: asyncpg.Pool,
    redis: Redis,
    *,
    profile_id: UUID,
    entity_id: UUID | None = None,
) -> ComposedDocsResponse:
    """Benchmark docs using composable infra functions.

    Flow:
      1. resolve_profile_identity_context -> profile check
      2. Entry docs fetch
      3. Assemble ComposedDocsResponse with permissions + API operations
    """
    from fastapi import HTTPException

    # -- Step 1: Profile context -----------------------------------------------

    profile = await resolve_profile_identity_context(pool, profile_id, redis)

    if profile is None:
        raise HTTPException(
            status_code=401,
            detail="Profile not found. Please sign in again.",
        )

    # -- Step 2: Entry docs ----------------------------------------------------

    async def _get_benchmark_docs() -> object:
        async with pool.acquire() as conn:
            return await get_benchmark_docs(conn)

    (benchmark_entry,) = await asyncio.gather(
        _get_benchmark_docs(),
    )

    # -- Page metadata ---------------------------------------------------------

    page_metadata = compute_docs_metadata(_PAGE_METADATA)

    # -- Step 3: Assemble response ---------------------------------------------

    # Lazy imports to avoid circular dependencies
    from app.infra.benchmark.permissions import (
        compute_benchmark_eval_status,
    )
    from app.routes.v5.benchmark.export import export_benchmark
    from app.routes.v5.benchmark.get import get_benchmark
    from app.routes.v5.benchmark.refresh import benchmark_refresh
    from app.routes.v5.benchmark.search import search_benchmark_history

    return ComposedDocsResponse(
        name="benchmark",
        type="analytics",
        description=(
            "Benchmark analytics evaluates AI model performance across "
            "standardized test scenarios with scoring and comparison metrics."
        ),
        entries=[benchmark_entry],
        resources=[],
        permissions=[
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
    )
