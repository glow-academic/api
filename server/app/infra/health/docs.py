"""Health docs logic — composable infra architecture.

Composes existing black-box tool docs:
  1. resolve_profile_identity_context — profile (role, departments)
  2. Entry tool docs — health entry tables, operations
  3. API operations — all public route handlers introspected
"""

from __future__ import annotations

import asyncio
from uuid import UUID

import asyncpg
from redis.asyncio import Redis

from app.infra.docs.get_operation_info import get_operation_info
from app.infra.docs.types import ComposedDocsResponse, DocsResponse
from app.infra.docs_helper import PageMetadataConfig, compute_docs_metadata
from app.infra.profile_identity_context import resolve_profile_identity_context

# Entry tool docs
from app.tools.entries.health.docs import get_health_docs

_PAGE_METADATA = PageMetadataConfig(
    list_title="Health",
    list_description="Monitor system performance and health.",
    detail_title="Health",
    detail_description="View system health metrics and status.",
    new_title="Health",
    new_description="Monitor system performance and health.",
)


async def docs_health_impl(
    pool: asyncpg.Pool,
    redis: Redis,
    *,
    profile_id: UUID,
    entity_id: UUID | None = None,
) -> ComposedDocsResponse:
    """Health docs using composable infra functions.

    Flow:
      1. resolve_profile_identity_context -> profile check
      2. Parallel: entry docs
      3. Assemble ComposedDocsResponse with API operations
    """
    from fastapi import HTTPException

    # -- Step 1: Profile context ------------------------------------------

    profile = await resolve_profile_identity_context(pool, profile_id, redis)

    if profile is None:
        raise HTTPException(
            status_code=401,
            detail="Profile not found. Please sign in again.",
        )

    # -- Step 2: Parallel docs fetches ------------------------------------

    async def _fetch_health_docs() -> DocsResponse:
        async with pool.acquire() as conn:
            return await get_health_docs(conn)

    (health,) = await asyncio.gather(
        _fetch_health_docs(),
    )

    # -- Page metadata -----------------------------------------------------

    page_metadata = compute_docs_metadata(_PAGE_METADATA)

    # -- Step 3: Assemble response ----------------------------------------

    # Lazy imports to avoid circular dependencies
    from app.routes.v5.health.export import export_health
    from app.routes.v5.health.get import get_health
    from app.routes.v5.health.refresh import health_refresh

    return ComposedDocsResponse(
        name="health",
        type="analytics",
        description=(
            "Health analytics monitors system performance metrics, "
            "service health indicators, and operational status."
        ),
        entries=[health],
        resources=[],
        permissions=[],
        api_operations=[
            get_operation_info(
                get_health,
                description="POST /get — Get system health metrics and status.",
            ),
            get_operation_info(
                health_refresh,
                description="POST /refresh — Refresh health materialized views.",
            ),
            get_operation_info(
                export_health,
                description="POST /export — Export health data as CSV/ZIP.",
            ),
        ],
        page_metadata=page_metadata,
    )
