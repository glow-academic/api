"""Chat page context — docs + profile identity + evaluated permissions.

Superset of docs.py. A single endpoint that gives the client everything
it needs to render the chat page:
  1. resolve_profile_identity_context — who you are (name, role, departments)
  2. Entry/resource docs — schema introspection (same as docs.py)
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
    OperationPrompts,
    StarterPrompt,
)
from app.infra.docs.build_profile_summary import build_profile_summary
from app.infra.docs_helper import PageMetadataConfig, compute_docs_metadata
from app.infra.profile_identity_context import resolve_profile_identity_context

# Entry tool docs
from app.tools.entries.chat.docs import get_chat_docs
from app.tools.entries.chat_drafts.docs import get_chat_drafts_docs

# Resource tool docs
from app.tools.resources.departments.docs import get_departments_docs
from app.tools.resources.descriptions.docs import get_descriptions_docs
from app.tools.resources.documents.docs import get_documents_docs
from app.tools.resources.fields.docs import get_fields_docs
from app.tools.resources.flags.docs import get_flags_docs
from app.tools.resources.images.docs import get_images_docs
from app.tools.resources.names.docs import get_names_docs
from app.tools.resources.objectives.docs import get_objectives_docs
from app.tools.resources.options.docs import get_options_docs
from app.tools.resources.parameter_fields.docs import (
    get_parameter_fields_docs,
)
from app.tools.resources.personas.docs import get_personas_docs
from app.tools.resources.problem_statements.docs import (
    get_problem_statements_docs,
)
from app.tools.resources.questions.docs import get_questions_docs
from app.tools.resources.scenarios.docs import get_scenarios_docs
from app.tools.resources.videos.docs import get_videos_docs

from app.utils.cache.big import (
    DEFAULT_BIG_CACHE_TTL_S,
    big_cache_key,
    get_or_build,
)

_PAGE_METADATA = PageMetadataConfig(
    list_title="Training",
    list_description="View simulation conversation analytics.",
    detail_title="Training Chat",
    detail_description="View chat messages, scoring, and rubric evaluations.",
    new_title="Training",
    new_description="View simulation conversation analytics.",
)


async def page_context_chat_impl(
    pool: asyncpg.Pool,
    redis: Redis,
    *,
    profile_id: UUID,
    entity_id: UUID | None = None,
    bypass_cache: bool = False,
    **_kwargs,
) -> ComposedContextResponse:
    """chat page context — big-cache wrapped."""
    return await get_or_build(
        redis=redis,
        key=big_cache_key("chat/page_context", {
            "profile_id": str(profile_id),
            "entity_id": str(entity_id) if entity_id else None,
        }),
        tags=["context", "chat", "artifacts"],
        ttl_s=DEFAULT_BIG_CACHE_TTL_S,
        response_model=ComposedContextResponse,
        builder=lambda: _page_context_chat_build(
            pool, redis,
            profile_id=profile_id,
            entity_id=entity_id,
        ),
        bypass_cache=bypass_cache,
    )


async def _page_context_chat_build(
    pool: asyncpg.Pool,
    redis: Redis,
    *,
    profile_id: UUID,
    entity_id: UUID | None = None,
) -> ComposedContextResponse:
    """Chat page context.

    Flow:
      1. resolve_profile_identity_context -> profile identity (kept, not discarded)
      2. Parallel: entry docs + all resource docs
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
    # Each branch acquires its own connection from the pool.

    async def _get_chat_docs() -> list:
        async with pool.acquire() as conn:
            return await get_chat_docs(conn)

    async def _get_chat_drafts_docs() -> list:
        async with pool.acquire() as conn:
            return await get_chat_drafts_docs(conn)

    async def _get_names_docs() -> list:
        async with pool.acquire() as conn:
            return await get_names_docs(conn)

    async def _get_descriptions_docs() -> list:
        async with pool.acquire() as conn:
            return await get_descriptions_docs(conn)

    async def _get_flags_docs() -> list:
        async with pool.acquire() as conn:
            return await get_flags_docs(conn)

    async def _get_departments_docs() -> list:
        async with pool.acquire() as conn:
            return await get_departments_docs(conn)

    async def _get_personas_docs() -> list:
        async with pool.acquire() as conn:
            return await get_personas_docs(conn)

    async def _get_documents_docs() -> list:
        async with pool.acquire() as conn:
            return await get_documents_docs(conn)

    async def _get_scenarios_docs() -> list:
        async with pool.acquire() as conn:
            return await get_scenarios_docs(conn)

    async def _get_fields_docs() -> list:
        async with pool.acquire() as conn:
            return await get_fields_docs(conn)

    async def _get_parameter_fields_docs() -> list:
        async with pool.acquire() as conn:
            return await get_parameter_fields_docs(conn)

    async def _get_questions_docs() -> list:
        async with pool.acquire() as conn:
            return await get_questions_docs(conn)

    async def _get_options_docs() -> list:
        async with pool.acquire() as conn:
            return await get_options_docs(conn)

    async def _get_videos_docs() -> list:
        async with pool.acquire() as conn:
            return await get_videos_docs(conn)

    async def _get_images_docs() -> list:
        async with pool.acquire() as conn:
            return await get_images_docs(conn)

    async def _get_problem_statements_docs() -> list:
        async with pool.acquire() as conn:
            return await get_problem_statements_docs(conn)

    async def _get_objectives_docs() -> list:
        async with pool.acquire() as conn:
            return await get_objectives_docs(conn)

    (
        chat_entry,
        chat_drafts,
        names,
        descriptions,
        flags,
        departments,
        personas,
        documents,
        scenarios,
        fields,
        parameter_fields,
        questions,
        options,
        videos,
        images,
        problem_statements,
        objectives,
    ) = await asyncio.gather(
        _get_chat_docs(),
        _get_chat_drafts_docs(),
        _get_names_docs(),
        _get_descriptions_docs(),
        _get_flags_docs(),
        _get_departments_docs(),
        _get_personas_docs(),
        _get_documents_docs(),
        _get_scenarios_docs(),
        _get_fields_docs(),
        _get_parameter_fields_docs(),
        _get_questions_docs(),
        _get_options_docs(),
        _get_videos_docs(),
        _get_images_docs(),
        _get_problem_statements_docs(),
        _get_objectives_docs(),
    )

    # -- Step 3: Page metadata --------------------------------------------------

    page_metadata = compute_docs_metadata(_PAGE_METADATA)

    # -- Step 4: Evaluate caller permissions ------------------------------------

    from app.infra.attempt.chat.permissions import (
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

    # Chat is analytics — no entity-level create/duplicate/delete.
    # can_draft is always True for authenticated users viewing chat.
    caller_permissions = CallerPermissions(
        can_create=False,
        can_draft=True,
        can_duplicate=False,
    )

    # -- Step 5: Build profile summary ------------------------------------------

    profile_summary = await build_profile_summary(pool, redis, profile)

    # -- Step 6: Starter prompts --------------------------------------------------

    prompts = OperationPrompts(prompts={
        "get": [
            StarterPrompt(title="View chat", content="Show the full message history, scoring, and rubric evaluations for this chat."),
            StarterPrompt(title="Analyze responses", content="Break down the quality and scoring of responses in this conversation."),
            StarterPrompt(title="Review rubric", content="Show how this chat performed against each rubric criterion."),
        ],
        "export": [
            StarterPrompt(title="Export transcript", content="Export the chat transcript with messages and scoring as CSV."),
            StarterPrompt(title="Download evaluation", content="Generate a downloadable report of rubric evaluations and scores."),
        ],
        "refresh": [
            StarterPrompt(title="Refresh chat data", content="Refresh the chat materialized views to reflect the latest messages."),
            StarterPrompt(title="Update scores", content="Rebuild chat analytics to include recently completed evaluations."),
        ],
    })

    # -- Step 7: Assemble response ----------------------------------------------

    # Lazy imports to avoid circular dependencies
    from app.routes.attempt.draft import patch_chat_draft
    from app.routes.chat.export import export_chat
    from app.routes.chat.get import chat_get
    from app.routes.chat.refresh import chat_refresh

    return ComposedContextResponse(
        name="chat",
        type="analytics",
        description=(
            "Chat analytics provides detailed views of simulation conversations "
            "including messages, scoring, rubric evaluations, and completion "
            "tracking."
        ),
        artifact=None,
        entries=[chat_entry, chat_drafts],
        resources=[
            names,
            descriptions,
            flags,
            departments,
            personas,
            documents,
            scenarios,
            fields,
            parameter_fields,
            questions,
            options,
            videos,
            images,
            problem_statements,
            objectives,
        ],
        permission_docs=[
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
        prompts=prompts,
        profile=profile_summary,
        caller_permissions=caller_permissions,
    )
