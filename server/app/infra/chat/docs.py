"""Chat docs logic — composable infra architecture.

Composes existing black-box tool docs:
  1. resolve_profile_identity_context — profile (role, departments)
  2. Entry tool docs — chat entries
  3. Permission functions — mode, scoring, status, display logic
  4. API operations — all public route handlers introspected
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
from app.tools.entries.chat.docs import get_chat_docs

_PAGE_METADATA = PageMetadataConfig(
    list_title="Training",
    list_description="View simulation conversation analytics.",
    detail_title="Training Chat",
    detail_description="View chat messages, scoring, and rubric evaluations.",
    new_title="Training",
    new_description="View simulation conversation analytics.",
)


async def docs_chat_impl(
    pool: asyncpg.Pool,
    redis: Redis,
    *,
    profile_id: UUID,
    entity_id: UUID | None = None,
) -> ComposedDocsResponse:
    """Chat docs using composable infra functions.

    Flow:
      1. resolve_profile_identity_context -> profile check
      2. Entry docs fetch
      3. Assemble ComposedDocsResponse with permissions + API operations
    """
    from fastapi import HTTPException

    # -- Step 1: Profile context -----------------------------------------------

    profile = await resolve_profile_identity_context(pool, profile_id, redis)

    if profile is None:
        raise HTTPException(
            status_code=401,
            detail="Profile not found. Please sign in again.",
        )

    # -- Step 2: Entry docs ----------------------------------------------------

    async def _get_chat_docs() -> object:
        async with pool.acquire() as conn:
            return await get_chat_docs(conn)

    (chat_entry,) = await asyncio.gather(
        _get_chat_docs(),
    )

    # -- Page metadata ---------------------------------------------------------

    page_metadata = compute_docs_metadata(_PAGE_METADATA)

    # -- Step 3: Assemble response ---------------------------------------------

    # Lazy imports to avoid circular dependencies
    from app.infra.chat.permissions import (
        compute_bundle_section_show,
        compute_completion_pct,
        compute_mode,
        compute_pass_pct,
        compute_score_status,
        compute_show_continue,
        compute_show_view,
        compute_status,
        compute_status_instructional,
        format_cohort_names,
    )
    from app.routes.v5.chat.draft import patch_chat_draft
    from app.routes.v5.chat.export import export_chat
    from app.routes.v5.chat.get import chat_get
    from app.routes.v5.chat.refresh import chat_refresh

    return ComposedDocsResponse(
        name="chat",
        type="analytics",
        description=(
            "Chat analytics provides detailed views of simulation conversations "
            "including messages, scoring, rubric evaluations, and completion "
            "tracking."
        ),
        entries=[chat_entry],
        resources=[],
        permissions=[
            get_operation_info(
                compute_mode,
                description="Determine view mode from practice flag and user role.",
            ),
            get_operation_info(
                compute_score_status,
                description="Classify score into high/medium/low status.",
            ),
            get_operation_info(
                compute_pass_pct,
                description="Calculate pass percentage from rubric points.",
            ),
            get_operation_info(
                compute_status,
                description="Determine simulation status (passed/in-progress/not-started).",
            ),
            get_operation_info(
                compute_status_instructional,
                description="Determine simulation status for instructional mode.",
            ),
            get_operation_info(
                compute_completion_pct,
                description="Calculate completion percentage for instructional mode.",
            ),
            get_operation_info(
                format_cohort_names,
                description="Format cohort names as a natural language list.",
            ),
            get_operation_info(
                compute_show_view,
                description="Determine if an attempt can be viewed.",
            ),
            get_operation_info(
                compute_show_continue,
                description="Determine if an attempt can be continued.",
            ),
            get_operation_info(
                compute_bundle_section_show,
                description="Determine if a bundle section should be visible.",
            ),
        ],
        api_operations=[
            get_operation_info(
                chat_get,
                description="POST /get — Get a single chat bundle with messages and scoring.",
            ),
            get_operation_info(
                patch_chat_draft,
                description="PATCH /draft — Create or patch a chat draft.",
            ),
            get_operation_info(
                chat_refresh,
                description="POST /refresh — Refresh chat materialized views.",
            ),
            get_operation_info(
                export_chat,
                description="POST /export — Export chat data as CSV.",
            ),
        ],
        page_metadata=page_metadata,
    )
