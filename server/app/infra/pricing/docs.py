"""Pricing docs logic — composable infra architecture.

Composes existing black-box tool docs:
  1. resolve_profile_identity_context — profile (role, departments)
  2. Entry tool docs — run pricing entry operations
  3. API operations — all public route handlers introspected
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

# Entry tool docs
from app.tools.entries.run_pricing.docs import get_run_pricing_docs

_PAGE_METADATA = PageMetadataConfig(
    list_title="Pricing",
    list_description="Track AI model usage costs and trends.",
    detail_title="Pricing",
    detail_description="View pricing analytics with cost breakdowns.",
    new_title="Pricing",
    new_description="View pricing analytics with cost breakdowns.",
)


async def docs_pricing_impl(
    pool: asyncpg.Pool,
    redis: Redis,
    *,
    profile_id: UUID,
    entity_id: UUID | None = None,
) -> ComposedDocsResponse:
    """Pricing docs using composable infra functions.

    Flow:
      1. resolve_profile_identity_context → profile check
      2. Parallel: entry docs
      3. Assemble ComposedDocsResponse with API operations
    """
    from fastapi import HTTPException

    # ── Step 1: Profile context ────────────────────────────────────────

    profile = await resolve_profile_identity_context(pool, profile_id, redis)

    if profile is None:
        raise HTTPException(
            status_code=401,
            detail="Profile not found. Please sign in again.",
        )

    # ── Step 2: Parallel docs fetches ──────────────────────────────────

    async with pool.acquire() as conn:
        (run_pricing,) = await asyncio.gather(
            get_run_pricing_docs(conn),
        )

    # ── Page metadata ───────────────────────────────────────────────────
    page_metadata = compute_docs_metadata(_PAGE_METADATA)

    # ── Step 3: Assemble response ──────────────────────────────────────

    # Lazy imports to avoid circular dependencies
    from app.routes.v5.pricing.export import export_pricing
    from app.routes.v5.pricing.get import get_pricing
    from app.routes.v5.pricing.refresh import pricing_refresh
    from app.routes.v5.pricing.search import search_pricing

    return ComposedDocsResponse(
        name="pricing",
        type="analytics",
        description=(
            "Pricing analytics tracks AI model usage costs, run pricing "
            "breakdowns, and cost trends across simulations."
        ),
        entries=[run_pricing],
        resources=[],
        permissions=[],
        api_operations=[
            get_operation_info(
                get_pricing,
                description="POST /get — Get pricing analytics with cost breakdowns.",
            ),
            get_operation_info(
                search_pricing,
                description="POST /search — Search pricing history entries.",
            ),
            get_operation_info(
                pricing_refresh,
                description="POST /refresh — Refresh pricing materialized views.",
            ),
            get_operation_info(
                export_pricing,
                description="POST /export — Export pricing data as CSV/ZIP.",
            ),
        ],
        page_metadata=page_metadata,
    )
