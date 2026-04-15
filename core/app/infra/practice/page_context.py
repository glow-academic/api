"""Practice page context — docs + profile identity + evaluated permissions.

Superset of docs.py. A single endpoint that gives the client everything
it needs to render the practice page:
  1. resolve_profile_identity_context — who you are (name, role, departments)
  2. Entry tool docs — practice entry tables, MV, connections, operations
  3. Permission evaluation — concrete booleans for THIS caller
  4. API operations — all public route handlers introspected
  5. Page metadata — titles and descriptions for list/detail/new views
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
    ProfileSummary,
)
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


async def page_context_practice_impl(
    pool: asyncpg.Pool,
    redis: Redis,
    *,
    profile_id: UUID,
    entity_id: UUID | None = None,
    **_kwargs,
) -> ComposedContextResponse:
    """Practice page context — superset of docs_practice_impl.

    Flow:
      1. resolve_profile_identity_context -> profile identity (kept, not discarded)
      2. Parallel: entry docs
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

    async def _get_practice_docs() -> object:
        async with pool.acquire() as conn:
            return await get_practice_docs(conn)

    (practice,) = await asyncio.gather(
        _get_practice_docs(),
    )

    # -- Step 3: Page metadata --------------------------------------------------

    page_metadata = compute_docs_metadata(_PAGE_METADATA)

    # -- Step 4: Evaluate caller permissions ------------------------------------
    # Practice is analytics — no entity-level create/draft/duplicate.
    # CallerPermissions still populated for sidebar/nav consistency.

    caller_permissions = CallerPermissions(
        can_create=False,
        can_draft=False,
        can_duplicate=False,
    )

    # -- Step 5: Build profile summary ------------------------------------------

    profile_summary = ProfileSummary(
        name=profile.name,
        role=profile.role,
        role_level=profile.role_level,
        department_ids=profile.department_ids,
        artifact_access=profile.role_artifacts,
        is_active=profile.is_active,
    )

    # -- Step 6: Assemble response ----------------------------------------------

    # Lazy imports to avoid circular dependencies
    from app.routes.practice.export import export_practice
    from app.routes.practice.get import practice_get
    from app.routes.practice.refresh import practice_refresh
    from app.routes.practice.search import search_practice

    return ComposedContextResponse(
        name="practice",
        type="analytics",
        description=(
            "Practice analytics provides self-directed simulation practice views "
            "with history, completion stats, and progress tracking."
        ),
        artifact=None,
        entries=[practice],
        resources=[],
        permission_docs=[],
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
                practice_refresh,
                description="POST /refresh — Refresh practice materialized views.",
            ),
            get_operation_info(
                export_practice,
                description="POST /export — Export practice data as CSV/ZIP.",
            ),
        ],
        page_metadata=page_metadata,
        profile=profile_summary,
        caller_permissions=caller_permissions,
    )
