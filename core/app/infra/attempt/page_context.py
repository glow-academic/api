"""Attempt page context — docs + profile identity + evaluated permissions.

Superset of docs.py. A single endpoint that gives the client everything
it needs to render the attempt page:
  1. resolve_profile_identity_context — who you are (name, role, departments)
  2. Entry docs — schema introspection (same as docs.py)
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
from app.tools.entries.attempt.docs import get_attempt_docs

_PAGE_METADATA = PageMetadataConfig(
    list_title="Attempts",
    list_description="View simulation attempt history and results.",
    detail_title="Attempt",
    detail_description="View detailed attempt with chat history and scoring.",
    new_title="Attempt",
    new_description="View simulation attempt history and results.",
)


async def page_context_attempt_impl(
    pool: asyncpg.Pool,
    redis: Redis,
    *,
    profile_id: UUID,
    entity_id: UUID | None = None,
    **_kwargs,
) -> ComposedContextResponse:
    """Attempt page context — superset of docs_attempt_impl.

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

    async def _fetch_attempt_docs() -> object:
        async with pool.acquire() as c:
            return await get_attempt_docs(c)

    (attempt_entry,) = await asyncio.gather(
        _fetch_attempt_docs(),
    )

    # -- Step 3: Page metadata --------------------------------------------------

    page_metadata = compute_docs_metadata(_PAGE_METADATA)

    # -- Step 4: Evaluate caller permissions ------------------------------------

    from app.infra.attempt.permissions import (
        check_attempt_access,
        compute_achieved_standards,
        compute_attempt_aggregates,
        compute_chat_position_and_current,
        compute_content_display,
        compute_continuation_options,
        compute_current_chat_index,
        compute_passed_standards,
        compute_percentage,
        compute_total_possible_points,
        compute_total_time_limit,
    )

    # Attempt is analytics — no create/draft/duplicate semantics.
    # Permissions are runtime (owner vs role hierarchy), not RBAC on departments.
    caller_permissions = CallerPermissions(
        can_create=False,
        can_draft=False,
        can_duplicate=False,
    )

    # -- Step 5: Build profile summary ------------------------------------------

    profile_summary = await build_profile_summary(pool, redis, profile)

    # -- Step 6: Assemble response ----------------------------------------------

    # Lazy imports to avoid circular dependencies
    from app.routes.attempt.archive import archive_attempts
    from app.routes.attempt.export import export_attempt
    from app.routes.attempt.get import attempt_get

    return ComposedContextResponse(
        name="attempt",
        type="analytics",
        description=(
            "Attempt analytics provides detailed views of simulation attempts "
            "including chat history, scoring, standards achievement, and "
            "completion status."
        ),
        artifact=None,
        entries=[attempt_entry],
        resources=[],
        permission_docs=[
            get_operation_info(
                check_attempt_access,
                description="Check if the requesting user has access to the attempt.",
            ),
            get_operation_info(
                compute_content_display,
                description="Compute display name, color, and icon for a content item.",
            ),
            get_operation_info(
                compute_chat_position_and_current,
                description="Compute position and is_current for each chat in-place.",
            ),
            get_operation_info(
                compute_attempt_aggregates,
                description="Compute attempt-level aggregates from chats.",
            ),
            get_operation_info(
                compute_total_possible_points,
                description="Compute total possible points from completed chats.",
            ),
            get_operation_info(
                compute_percentage,
                description="Compute percentage score.",
            ),
            get_operation_info(
                compute_current_chat_index,
                description="Compute the current chat index.",
            ),
            get_operation_info(
                compute_total_time_limit,
                description="Compute total time limit from all chats.",
            ),
            get_operation_info(
                compute_achieved_standards,
                description="Derive achieved standards from feedbacks.",
            ),
            get_operation_info(
                compute_passed_standards,
                description="Derive passed standards from feedbacks and pass_points.",
            ),
            get_operation_info(
                compute_continuation_options,
                description="Compute available continuation options from previous attempt chats.",
            ),
        ],
        api_operations=[
            get_operation_info(
                attempt_get,
                description="POST /get — Get a single attempt with full detail.",
            ),
            get_operation_info(
                archive_attempts,
                description="POST /archive — Archive completed attempts.",
            ),
            get_operation_info(
                export_attempt,
                description="POST /export — Export attempt data as CSV/ZIP.",
            ),
        ],
        page_metadata=page_metadata,
        profile=profile_summary,
        caller_permissions=caller_permissions,
    )
