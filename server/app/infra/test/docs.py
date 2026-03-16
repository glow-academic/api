"""Test docs logic — composable infra architecture.

Composes existing black-box tool docs:
  1. resolve_profile_identity_context — profile (role, departments)
  2. Entry tool docs — test entry documentation
  3. Permission functions — introspected via get_operation_info
  4. API operations — all public route handlers introspected
"""

from __future__ import annotations

from uuid import UUID

import asyncpg
from redis.asyncio import Redis

from app.infra.docs.get_operation_info import get_operation_info
from app.infra.docs.types import ComposedDocsResponse
from app.infra.docs_helper import PageMetadataConfig, compute_docs_metadata
from app.infra.profile_identity_context import resolve_profile_identity_context

# Entry tool docs
from app.tools.entries.test.docs import get_test_docs

_PAGE_METADATA = PageMetadataConfig(
    list_title="Tests",
    list_description="View benchmark test configurations.",
    detail_title="Test",
    detail_description="View test invocations and evaluation results.",
    new_title="Test",
    new_description="View test invocations and evaluation results.",
)


async def docs_test_impl(
    pool: asyncpg.Pool,
    redis: Redis,
    *,
    profile_id: UUID,
    entity_id: UUID | None = None,
) -> ComposedDocsResponse:
    """Test docs using composable infra functions.

    Flow:
      1. resolve_profile_identity_context -> profile check
      2. Parallel: entry docs fetch
      3. Assemble ComposedDocsResponse with permissions + API operations
    """
    from fastapi import HTTPException

    # -- Step 1: Profile context ------------------------------------------

    profile = await resolve_profile_identity_context(pool, profile_id, redis)

    if profile is None:
        raise HTTPException(
            status_code=401,
            detail="Profile not found. Please sign in again.",
        )

    # -- Step 2: Entry docs fetch -----------------------------------------

    async with pool.acquire() as conn:
        test_entry = await get_test_docs(conn)

    # ── Page metadata ───────────────────────────────────────────────────
    page_metadata = compute_docs_metadata(_PAGE_METADATA)

    # -- Step 3: Assemble response ----------------------------------------

    # Lazy imports to avoid circular dependencies
    from app.infra.test.permissions import compute_test_status
    from app.routes.v5.test.archive import archive_test_artifacts
    from app.routes.v5.test.export import export_test
    from app.routes.v5.test.get import get_test_artifact

    return ComposedDocsResponse(
        name="test",
        type="analytics",
        description=(
            "Test analytics provides detailed views of benchmark test "
            "configurations including invocations, runs, and evaluation results."
        ),
        entries=[test_entry],
        resources=[],
        permissions=[
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
    )
