"""Practice docs logic — composable infra architecture.

Composes existing black-box tool docs:
  1. resolve_profile_identity_context — profile (role, departments)
  2. Entry tool docs — practice entry operations
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
from app.tools.entries.practice.docs import get_practice_docs

_PAGE_METADATA = PageMetadataConfig(
    list_title="Practice",
    list_description="View self-directed simulation practice history.",
    detail_title="Practice",
    detail_description="View practice stats and progress tracking.",
    new_title="Practice",
    new_description="View practice stats and progress tracking.",
)


async def docs_practice_client(
    pool: asyncpg.Pool,
    redis: Redis,
    *,
    profile_id: UUID,
    entity_id: UUID | None = None,
) -> ComposedDocsResponse:
    """Practice docs using composable infra functions.

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

    async def _get_practice_docs() -> object:
        async with pool.acquire() as conn:
            return await get_practice_docs(conn)

    (practice,) = await asyncio.gather(
        _get_practice_docs(),
    )

    # ── Page metadata ───────────────────────────────────────────────────
    page_metadata = compute_docs_metadata(_PAGE_METADATA)

    # ── Step 3: Assemble response ──────────────────────────────────────

    # Lazy imports to avoid circular dependencies
    from app.routes.v5.practice.export import export_practice
    from app.routes.v5.practice.get import practice_get
    from app.routes.v5.practice.search import search_practice

    return ComposedDocsResponse(
        name="practice",
        type="analytics",
        description=(
            "Practice analytics provides self-directed simulation practice views "
            "with history, completion stats, and progress tracking."
        ),
        entries=[practice],
        resources=[],
        permissions=[],
        api_operations=[
            get_operation_info(
                practice_get,
                description="POST /get — Get practice dashboard with personal stats.",
            ),
            get_operation_info(
                search_practice,
                description="POST /search — Search practice history entries.",
            ),
            get_operation_info(
                export_practice,
                description="POST /export — Export practice data as CSV/ZIP.",
            ),
        ],
        page_metadata=page_metadata,
    )
