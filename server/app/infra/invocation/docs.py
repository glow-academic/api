"""Invocation docs logic — composable infra architecture.

Composes existing black-box tool docs:
  1. resolve_profile_identity_context — profile (role, departments)
  2. Entry tool docs — invocation entry operations
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
from app.tools.entries.invocation.docs import get_invocation_docs

_PAGE_METADATA = PageMetadataConfig(
    list_title="Invocations",
    list_description="View test invocation results and drafts.",
    detail_title="Invocation",
    detail_description="View invocation execution details and run history.",
    new_title="Invocation",
    new_description="View invocation execution details and run history.",
)


async def docs_invocation_impl(
    pool: asyncpg.Pool,
    redis: Redis,
    *,
    profile_id: UUID,
    entity_id: UUID | None = None,
) -> ComposedDocsResponse:
    """Invocation docs using composable infra functions.

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

    async def _get_invocation_docs() -> object:
        async with pool.acquire() as conn:
            return await get_invocation_docs(conn)

    (invocation,) = await asyncio.gather(
        _get_invocation_docs(),
    )

    # ── Page metadata ───────────────────────────────────────────────────
    page_metadata = compute_docs_metadata(_PAGE_METADATA)

    # ── Step 3: Assemble response ──────────────────────────────────────

    # Lazy imports to avoid circular dependencies
    from app.routes.v5.invocation.draft import patch_invocation_draft
    from app.routes.v5.invocation.export import export_invocation
    from app.routes.v5.invocation.get import invocation_get

    return ComposedDocsResponse(
        name="invocation",
        type="analytics",
        description=(
            "Invocation analytics provides detailed views of test invocations "
            "including execution results, drafts, and run history."
        ),
        entries=[invocation],
        resources=[],
        permissions=[],
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
    )
