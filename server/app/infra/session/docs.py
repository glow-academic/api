"""Session docs logic — composable infra architecture.

Composes existing black-box tool docs:
  1. resolve_profile_identity_context — profile (role, departments)
  2. Entry tool docs — sessions entry documentation
  3. API operations — all public route handlers introspected
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
from app.tools.entries.sessions.docs import get_sessions_docs

_PAGE_METADATA = PageMetadataConfig(
    list_title="Sessions",
    list_description="View simulation session details.",
    detail_title="Session",
    detail_description="View session timeline with groups and run history.",
    new_title="Session",
    new_description="View session timeline with groups and run history.",
)


async def docs_session_impl(
    pool: asyncpg.Pool,
    redis: Redis,
    *,
    profile_id: UUID,
    entity_id: UUID | None = None,
) -> ComposedDocsResponse:
    """Session docs using composable infra functions.

    Flow:
      1. resolve_profile_identity_context -> profile check
      2. Parallel: entry docs fetch
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

    # -- Step 2: Entry docs fetch -----------------------------------------

    async with pool.acquire() as conn:
        sessions = await get_sessions_docs(conn)

    # ── Page metadata ───────────────────────────────────────────────────
    page_metadata = compute_docs_metadata(_PAGE_METADATA)

    # -- Step 3: Assemble response ----------------------------------------

    # Lazy imports to avoid circular dependencies
    from app.routes.v5.session.export import export_session
    from app.routes.v5.session.get import get_session

    return ComposedDocsResponse(
        name="session",
        type="analytics",
        description=(
            "Session analytics provides detailed views of simulation sessions "
            "including timelines, group results, and run history."
        ),
        entries=[sessions],
        resources=[],
        permissions=[],
        api_operations=[
            get_operation_info(
                get_session,
                description="POST /get — Get a single session with timeline and groups.",
            ),
            get_operation_info(
                export_session,
                description="POST /export — Export session data as CSV/ZIP.",
            ),
        ],
        page_metadata=page_metadata,
    )
