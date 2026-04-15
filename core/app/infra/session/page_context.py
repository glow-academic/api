"""Session page context — docs + profile identity + evaluated permissions.

Superset of docs.py. A single endpoint that gives the client everything
it needs to render the session page:
  1. resolve_profile_identity_context — who you are (name, role, departments)
  2. Entry docs — session entry schema introspection (same as docs.py)
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


async def page_context_session_impl(
    pool: asyncpg.Pool,
    redis: Redis,
    *,
    profile_id: UUID,
    entity_id: UUID | None = None,
    **_kwargs,
) -> ComposedContextResponse:
    """Session page context — superset of docs_session_impl.

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

    async def _fetch_sessions_docs() -> object:
        async with pool.acquire() as c:
            return await get_sessions_docs(c)

    (sessions,) = await asyncio.gather(
        _fetch_sessions_docs(),
    )

    # -- Step 3: Page metadata --------------------------------------------------

    page_metadata = compute_docs_metadata(_PAGE_METADATA)

    # -- Step 4: Evaluate caller permissions ------------------------------------
    # Session has no artifact-level permissions module; use simple role defaults.

    caller_permissions = CallerPermissions(
        can_create=False,
        can_draft=False,
        can_duplicate=False,
    )

    # -- Step 5: Build profile summary ------------------------------------------

    profile_summary = await build_profile_summary(pool, redis, profile)

    # -- Step 6: Assemble response ----------------------------------------------

    # Lazy imports to avoid circular dependencies
    from app.routes.session.export import export_session
    from app.routes.session.get import get_session

    return ComposedContextResponse(
        name="session",
        type="analytics",
        description=(
            "Session analytics provides detailed views of simulation sessions "
            "including timelines, group results, and run history."
        ),
        entries=[sessions],
        resources=[],
        permission_docs=[],
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
        profile=profile_summary,
        caller_permissions=caller_permissions,
    )
