"""Group docs logic — composable infra architecture.

Composes existing black-box tool docs:
  1. resolve_profile_identity_context — profile (role, departments)
  2. Entry tool docs — groups entry tables, MV, operations
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
from app.tools.entries.groups.docs import get_groups_docs

_PAGE_METADATA = PageMetadataConfig(
    list_title="Groups",
    list_description="View test invocation group results.",
    detail_title="Group",
    detail_description="View group runs and aggregated metrics.",
    new_title="Group",
    new_description="View test invocation group results.",
)


async def docs_group_impl(
    pool: asyncpg.Pool,
    redis: Redis,
    *,
    profile_id: UUID,
    entity_id: UUID | None = None,
) -> ComposedDocsResponse:
    """Group docs using composable infra functions.

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

    async def _fetch_groups_docs() -> DocsResponse:
        async with pool.acquire() as conn:
            return await get_groups_docs(conn)

    (groups,) = await asyncio.gather(
        _fetch_groups_docs(),
    )

    # -- Page metadata -----------------------------------------------------

    page_metadata = compute_docs_metadata(_PAGE_METADATA)

    # -- Step 3: Assemble response ----------------------------------------

    # Lazy imports to avoid circular dependencies
    from app.routes.v5.group.export import export_group
    from app.routes.v5.group.get import get_group

    return ComposedDocsResponse(
        name="group",
        type="analytics",
        description=(
            "Group analytics provides detailed views of test invocation groups "
            "including runs, results, and aggregated metrics."
        ),
        entries=[groups],
        resources=[],
        permissions=[],
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
    )
