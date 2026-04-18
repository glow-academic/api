"""Chat draft logic — canonical draft-first flow."""

from __future__ import annotations

from uuid import UUID

import asyncpg
from fastapi import HTTPException
from redis.asyncio import Redis

from app.infra.permissions_helpers import has_permission
from app.infra.profile_identity_context import resolve_profile_identity_context
from app.infra.chat.refresh import refresh_chat_impl
from app.infra.chat.types import (
    ChatDraftFormState,
    PatchChatDraftApiRequest,
    PatchChatDraftApiResponse,
    SaveChatFieldError,
)
from app.tools.entries.chat_drafts.create import create_chat_draft
from app.tools.entries.chat_drafts.get import get_chat_drafts
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


async def _resolve_creatable_values(
    pool: asyncpg.Pool,
    redis: Redis,
    request: PatchChatDraftApiRequest,
) -> list[SaveChatFieldError]:
    """Resolve raw value fields to resource IDs (mutates request in place)."""
    errors: list[SaveChatFieldError] = []

    async with pool.acquire() as conn:
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

        if request.objectives:
            created_ids = []
            for objective_text in request.objectives:
                result = await create_objective(conn, objective_text, redis)
                created_ids.append(result.id)
            request.objective_ids = (request.objective_ids or []) + created_ids

        if request.images:
            created_ids = []
            for image in request.images:
                result = await create_image(conn, image.name, image.description, redis)
                created_ids.append(result.id)
            request.image_ids = (request.image_ids or []) + created_ids

        if request.videos:
            created_ids = []
            for video in request.videos:
                result = await create_video(conn, video.name, video.description, redis)
                created_ids.append(result.id)
            request.video_ids = (request.video_ids or []) + created_ids

        if request.questions:
            created_ids = []
            for question in request.questions:
                result = await create_question(
                    conn,
                    question.question_text,
                    question.time,
                    redis,
                    allow_multiple=question.allow_multiple,
                )
                created_ids.append(result.id)
            request.question_ids = (request.question_ids or []) + created_ids

        if request.options:
            created_ids = []
            for option in request.options:
                result = await create_option(
                    conn,
                    option.option_text,
                    redis,
                    question_id=option.question_id,
                )
                created_ids.append(result.id)
            request.option_ids = (request.option_ids or []) + created_ids

    return errors


async def patch_chat_draft_impl(
    pool: asyncpg.Pool,
    redis: Redis,
    *,
    profile_id: UUID,
    session_id: UUID,
    request: PatchChatDraftApiRequest,
    soft: bool = False,
    accept: bool | None = None,
    idempotency_key: UUID | None = None,
) -> PatchChatDraftApiResponse:
    """Persist canonical chat draft state and return server-authored form state."""
    resolved_draft_id = request.draft_id or request.input_draft_id
    idempotency_key = idempotency_key or request.idempotency_key or resolved_draft_id
    if accept is None and request.idempotency_key is not None:
        accept = request.accept

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

    if not has_permission(profile.role_permissions, "attempt", "chat_draft"):
        raise HTTPException(
            status_code=403,
            detail="You don't have permission to create or edit chat drafts.",
        )

    if accept is not None and idempotency_key is not None:
        if accept:
            async with pool.acquire() as conn:
                drafts = await get_chat_drafts(conn, [idempotency_key])
                async with conn.transaction():
                    if drafts:
                        draft = drafts[0]
                        await create_chat_draft(
                            conn,
                            session_id=session_id,
                            id=idempotency_key,
                            soft=False,
                            department_ids=draft.department_ids,
                            description_ids=draft.description_ids,
                            document_ids=draft.document_ids,
                            field_ids=draft.field_ids,
                            flag_ids=draft.flag_ids,
                            image_ids=draft.image_ids,
                            name_ids=draft.name_ids,
                            objective_ids=draft.objective_ids,
                            option_ids=draft.option_ids,
                            parameter_field_ids=draft.parameter_field_ids,
                            parameter_ids=draft.parameter_ids,
                            persona_ids=draft.persona_ids,
                            problem_statement_ids=draft.problem_statement_ids,
                            profile_ids=draft.profile_ids or [profile.profiles_id],
                            question_ids=draft.question_ids,
                            scenario_ids=draft.scenario_ids,
                            video_ids=draft.video_ids,
                            pending_ids=set(),
                        )
                    else:
                        await create_chat_draft(
                            conn,
                            session_id=session_id,
                            id=idempotency_key,
                            soft=False,
                            profile_ids=[profile.profiles_id],
                        )
            await refresh_chat_impl(
                pool,
                redis,
                profile_id=profile_id,
                session_id=session_id,
                targets=["chat_drafts_mv"],
                operation_key=idempotency_key,
            )
        return PatchChatDraftApiResponse(
            success=True,
            draft_id=idempotency_key,
            idempotency_key=idempotency_key,
            message="Draft accepted" if accept else "Draft rejected",
            form_state=ChatDraftFormState(),
        )

    errors = await _resolve_creatable_values(pool, redis, request)
    if errors:
        raise HTTPException(
            status_code=400,
            detail=[error.model_dump() for error in errors],
        )

    pending_ids = set(request.pending_ids or [])
    target_draft_id = resolved_draft_id or idempotency_key

    async with pool.acquire() as conn:
        async with conn.transaction():
            result = await create_chat_draft(
                conn,
                session_id=session_id,
                id=target_draft_id,
                soft=soft,
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

    await refresh_chat_impl(
        pool,
        redis,
        profile_id=profile_id,
        session_id=session_id,
        targets=["chat_drafts_mv"],
        soft=soft,
        operation_key=result.id,
    )

    return PatchChatDraftApiResponse(
        success=True,
        draft_id=result.id,
        idempotency_key=result.id,
        message="Draft created (pending acceptance)" if soft else "Draft created successfully",
        form_state=form_state,
    )
