"""Chat draft logic — composable infra architecture.

Core draft function that composes existing black-box tools:
  1. resolve_profile_identity_context — profile (role, departments)
  2. Value resolution (creatable resources only) — raw value → ID
  3. create_chat_draft — entry tool (append-only snapshot)
  4. Build form state (server is source of truth)
  5. refresh_chat_drafts — MV refresh
  6. invalidate_tags — cache invalidation
"""

from __future__ import annotations

from uuid import UUID

import asyncpg
from fastapi import HTTPException
from redis.asyncio import Redis

from app.infra.profile_identity_context import resolve_profile_identity_context
from app.infra.chat.types import (
    ChatDraftFormState,
    PatchChatDraftApiRequest,
    PatchChatDraftApiResponse,
    SaveChatFieldError,
)
from app.tools.entries.chat_drafts.create import create_chat_draft
from app.tools.entries.chat_drafts.refresh import refresh_chat_drafts
from app.tools.resources.descriptions.create import create_description
from app.tools.resources.descriptions.search import search_descriptions
from app.tools.resources.images.create import create_image
from app.tools.resources.names.create import create_name
from app.tools.resources.names.search import search_names
from app.tools.resources.objectives.create import create_objective
from app.tools.resources.options.create import create_option
from app.tools.resources.problem_statements.create import (
    create_problem_statement,
)
from app.tools.resources.problem_statements.search import search_problem_statements
from app.tools.resources.questions.create import create_question
from app.tools.resources.videos.create import create_video
from app.utils.cache.invalidate_tags import invalidate_tags

# ---------------------------------------------------------------------------
# Value resolution — creatable resources only
# ---------------------------------------------------------------------------


async def _resolve_creatable_values(
    pool: asyncpg.Pool,
    redis: Redis,
    request: PatchChatDraftApiRequest,
) -> list[SaveChatFieldError]:
    """Resolve raw value fields to resource IDs (mutates request in place).

    Single-select creatables: name, description, problem_statement
      → value creates resource, created ID is appended to the IDs list.

    Multi-select creatables: objectives, images, videos, questions, options
      → values create resources, created IDs are merged with existing IDs.

    Returns a list of errors (empty if all resolved).
    """
    errors: list[SaveChatFieldError] = []

    async with pool.acquire() as conn:
        # ── Single-select creatables ──────────────────────────────────────

        if request.name is not None and request.name_id is None:
            existing = await search_names(conn, redis, search=request.name, limit_count=1)
            if existing and existing[0].name.lower() == request.name.lower():
                request.name_id = existing[0].id
            else:
                result = await create_name(conn, request.name, redis)
                request.name_id = result.id

        if request.description is not None and request.description_id is None:
            existing = await search_descriptions(conn, redis, search=request.description, limit_count=1)
            if existing and existing[0].description.lower() == request.description.lower():
                request.description_id = existing[0].id
            else:
                result = await create_description(conn, request.description, redis)
                request.description_id = result.id

        if request.problem_statement is not None and request.problem_statement_id is None:
            existing = await search_problem_statements(
                conn, redis, search=request.problem_statement, limit_count=1
            )
            if (
                existing
                and existing[0].problem_statement.lower() == request.problem_statement.lower()
            ):
                request.problem_statement_id = existing[0].id
            else:
                result = await create_problem_statement(
                    conn, request.name or "", request.problem_statement, redis
                )
                request.problem_statement_id = result.id

        # ── Multi-select creatables (merged mode) ─────────────────────────

        if request.objectives:
            created_ids = []
            for obj_text in request.objectives:
                result = await create_objective(conn, obj_text, redis)
                created_ids.append(result.id)
            request.objective_ids = (request.objective_ids or []) + created_ids

        if request.images:
            created_ids = []
            for img in request.images:
                result = await create_image(conn, img.name, img.description, redis)
                created_ids.append(result.id)
            request.image_ids = (request.image_ids or []) + created_ids

        if request.videos:
            created_ids = []
            for vid in request.videos:
                result = await create_video(conn, vid.name, vid.description, redis)
                created_ids.append(result.id)
            request.video_ids = (request.video_ids or []) + created_ids

        if request.questions:
            created_ids = []
            for q in request.questions:
                result = await create_question(
                    conn,
                    q.question_text,
                    q.time,
                    redis,
                    allow_multiple=q.allow_multiple,
                )
                created_ids.append(result.id)
            request.question_ids = (request.question_ids or []) + created_ids

        if request.options:
            created_ids = []
            for opt in request.options:
                result = await create_option(
                    conn, opt.option_text, redis, question_id=opt.question_id
                )
                created_ids.append(result.id)
            request.option_ids = (request.option_ids or []) + created_ids

    return errors


# ---------------------------------------------------------------------------
# patch_chat_draft_impl — composable infra architecture
# ---------------------------------------------------------------------------


async def patch_chat_draft_impl(
    pool: asyncpg.Pool,
    redis: Redis,
    *,
    profile_id: UUID,
    session_id: UUID,
    request: PatchChatDraftApiRequest,
) -> PatchChatDraftApiResponse:
    """Chat draft using composable infra functions.

    Flow:
      1. resolve_profile_identity_context → role
      2. Value resolution (creatable resources only)
      3. create_chat_draft entry tool (append-only snapshot)
      4. Build form state (server is source of truth)
      5. refresh_chat_drafts MV
      6. invalidate_tags
    """

    draft_entry_id = request.draft_id or request.input_draft_id
    pending_ids = set(request.pending_ids or [])

    # ── Step 1: Profile context ────────────────────────────────────────

    profile = await resolve_profile_identity_context(
        pool,
        profile_id,
        redis,
        session_id=session_id,
    )

    if profile is None:
        raise HTTPException(
            status_code=401,
            detail="Profile not found. Please sign in again.",
        )

    # ── Step 2: Value resolution (creatable only) ──────────────────────

    errors = await _resolve_creatable_values(pool, redis, request)
    if errors:
        raise HTTPException(
            status_code=400,
            detail=[e.model_dump() for e in errors],
        )

    # ── Step 3: Create draft entry (append-only snapshot) ──────────────

    async with pool.acquire() as conn:
        async with conn.transaction():
            result = await create_chat_draft(
                conn,
                session_id=session_id,
                id=draft_entry_id,
                name_ids=[request.name_id] if request.name_id else None,
                description_ids=[request.description_id] if request.description_id else None,
                document_ids=request.document_ids,
                field_ids=request.field_ids,
                flag_ids=request.flag_ids,
                image_ids=request.image_ids,
                objective_ids=request.objective_ids,
                option_ids=request.option_ids,
                parameter_field_ids=request.parameter_field_ids,
                parameter_ids=request.parameter_ids,
                persona_ids=request.persona_ids,
                problem_statement_ids=[request.problem_statement_id] if request.problem_statement_id else None,
                question_ids=request.question_ids,
                scenario_ids=request.scenario_ids,
                video_ids=request.video_ids,
                department_ids=request.department_ids,
                profile_ids=[profile.profiles_id],
                pending_ids=pending_ids,
            )

    # ── Step 4: Build form state (server is source of truth) ──────────

    form_state = ChatDraftFormState(
        name_id=request.name_id,
        name=request.name,
        description_id=request.description_id,
        description=request.description,
        problem_statement_id=request.problem_statement_id,
        problem_statement=request.problem_statement,
        flag_ids=request.flag_ids or [],
        department_ids=request.department_ids or [],
        persona_ids=request.persona_ids or [],
        document_ids=request.document_ids or [],
        parameter_field_ids=request.parameter_field_ids or [],
        parameter_ids=request.parameter_ids or [],
        scenario_ids=request.scenario_ids or [],
        field_ids=request.field_ids or [],
        question_ids=request.question_ids or [],
        option_ids=request.option_ids or [],
        video_ids=request.video_ids or [],
        image_ids=request.image_ids or [],
        objective_ids=request.objective_ids or [],
        pending_ids=list(pending_ids),
    )

    # ── Step 5: Refresh MV ─────────────────────────────────────────────

    async with pool.acquire() as conn:
        await refresh_chat_drafts(conn)

    # ── Step 6: Invalidate cache ───────────────────────────────────────

    await invalidate_tags(["training", "drafts"], redis=redis)

    return PatchChatDraftApiResponse(
        success=True,
        draft_id=result.id,
        idempotency_key=request.idempotency_key,
        message="Draft created successfully",
        form_state=form_state,
    )
