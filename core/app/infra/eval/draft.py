"""Eval draft logic — canonical draft-first architecture."""

from __future__ import annotations

from typing import Any
from uuid import UUID

import asyncpg
from fastapi import HTTPException
from redis.asyncio import Redis

from app.infra.eval.permissions import compute_can_draft
from app.infra.eval.refresh import refresh_eval_impl
from app.infra.eval.types import (
    DraftFormState,
    PatchEvalDraftApiRequest,
    PatchEvalDraftApiResponse,
    SaveEvalFieldError,
)
from app.infra.profile_identity_context import resolve_profile_identity_context
from app.tools.entries.eval_drafts.create import create_eval_draft
from app.tools.entries.eval_drafts.get import get_eval_drafts
from app.tools.resources.departments.search import search_departments
from app.tools.resources.descriptions.create import create_description
from app.tools.resources.descriptions.search import search_descriptions
from app.tools.resources.names.create import create_name
from app.tools.resources.names.search import search_names


async def _resolve_creatable_values(
    conn: asyncpg.Connection,
    redis: Redis,
    request: PatchEvalDraftApiRequest,
) -> list[SaveEvalFieldError]:
    """Resolve raw values to resource IDs, mutating the request in place."""

    errors: list[SaveEvalFieldError] = []

    if request.name is not None and request.name_id is None:
        existing = await search_names(
            conn,
            redis,
            search=request.name,
            limit_count=1,
            eval=True,
        )
        match = next(
            (item for item in existing if item.name and item.name.lower() == request.name.lower()),
            None,
        )
        if match and match.id:
            request.name_id = match.id
        else:
            result = await create_name(conn, request.name, redis)
            request.name_id = result.id

    if request.description is not None and request.description_id is None:
        existing = await search_descriptions(
            conn,
            redis,
            search=request.description,
            limit_count=1,
            eval=True,
        )
        match = next(
            (
                item
                for item in existing
                if item.description and item.description.lower() == request.description.lower()
            ),
            None,
        )
        if match and match.id:
            request.description_id = match.id
        else:
            result = await create_description(conn, request.description, redis)
            request.description_id = result.id

    if request.departments is not None and request.department_ids is None:
        all_departments = await search_departments(
            conn,
            redis,
            search=None,
            limit_count=1000,
        )
        department_name_map = {
            item.name.lower(): item.department_id
            for item in all_departments
            if item.name and item.department_id
        }
        resolved_ids: list[UUID] = []
        for department_name in request.departments:
            department_id = department_name_map.get(department_name.lower())
            if department_id:
                resolved_ids.append(department_id)
            else:
                errors.append(
                    SaveEvalFieldError(
                        field="departments",
                        message=f'Department "{department_name}" not found',
                    )
                )
        if not any(error.field == "departments" for error in errors):
            request.department_ids = resolved_ids

    return errors


async def patch_eval_draft_impl(
    pool: asyncpg.Pool,
    redis: Redis,
    *,
    profile_id: UUID,
    session_id: UUID,
    request: PatchEvalDraftApiRequest | None = None,
    draft_id: UUID | None = None,
    soft: bool = False,
    accept: bool | None = None,
    idempotency_key: UUID | None = None,
    **kwargs: Any,
) -> PatchEvalDraftApiResponse:
    """Eval draft using the canonical request/response contract."""

    if request is None:
        request = PatchEvalDraftApiRequest(**kwargs)

    request.draft_id = request.draft_id or request.input_draft_id or draft_id
    request.input_draft_id = request.input_draft_id or request.draft_id

    resolved_draft_id = request.draft_id or request.input_draft_id
    idempotency_key = idempotency_key or request.idempotency_key or resolved_draft_id
    if idempotency_key is not None and accept is None:
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

    if not compute_can_draft(
        role_level=profile.role_level,
        role_permissions=profile.role_permissions,
    ):
        raise HTTPException(
            status_code=403,
            detail="You don't have permission to create or edit eval drafts.",
        )

    if accept is not None and idempotency_key is not None:
        if accept:
            async with pool.acquire() as conn:
                drafts = await get_eval_drafts(conn, [idempotency_key])
                if drafts:
                    draft = drafts[0]
                    async with conn.transaction():
                        await create_eval_draft(
                            conn,
                            session_id=session_id,
                            id=idempotency_key,
                            soft=False,
                            department_ids=draft.department_ids,
                            description_ids=draft.description_ids,
                            flag_ids=draft.flag_ids,
                            model_ids=draft.model_ids,
                            name_ids=draft.name_ids,
                            profile_ids=draft.profile_ids or [profile.profiles_id],
                            rubric_ids=draft.rubric_ids,
                            model_flag_ids=draft.model_flag_ids,
                            model_position_ids=draft.model_position_ids,
                            model_rubric_ids=draft.model_rubric_ids,
                            pending_ids=set(),
                        )
            await refresh_eval_impl(
                pool,
                redis,
                profile_id=profile_id,
                session_id=session_id,
                operation_key=idempotency_key,
            )

        return PatchEvalDraftApiResponse(
            success=True,
            draft_id=idempotency_key,
            idempotency_key=idempotency_key,
            message="Draft accepted" if accept else "Draft rejected",
            form_state=DraftFormState(),
        )

    async with pool.acquire() as conn:
        errors = await _resolve_creatable_values(conn, redis, request)
    if errors:
        raise HTTPException(
            status_code=400,
            detail=[error.model_dump() for error in errors],
        )

    async with pool.acquire() as conn:
        async with conn.transaction():
            result = await create_eval_draft(
                conn,
                session_id=session_id,
                id=resolved_draft_id or idempotency_key,
                soft=soft,
                name_ids=[request.name_id] if request.name_id else None,
                description_ids=[request.description_id] if request.description_id else None,
                flag_ids=request.flag_ids,
                department_ids=request.department_ids,
                model_ids=request.model_ids,
                model_flag_ids=request.model_flag_ids,
                model_position_ids=request.model_position_ids,
                model_rubric_ids=request.model_rubric_ids,
                profile_ids=[profile.profiles_id],
                pending_ids=set(request.pending_ids) if request.pending_ids else None,
            )

    form_state = DraftFormState(
        name_id=request.name_id,
        name=request.name,
        description_id=request.description_id,
        description=request.description,
        flag_ids=request.flag_ids or [],
        department_ids=request.department_ids or [],
        model_ids=request.model_ids or [],
        model_flag_ids=request.model_flag_ids or [],
        model_position_ids=request.model_position_ids or [],
        model_rubric_ids=request.model_rubric_ids or [],
        pending_ids=request.pending_ids or [],
    )

    if not soft:
        await refresh_eval_impl(
            pool,
            redis,
            profile_id=profile_id,
            session_id=session_id,
            soft=soft,
            operation_key=result.id,
        )

    return PatchEvalDraftApiResponse(
        success=True,
        draft_id=result.id,
        idempotency_key=result.id,
        message="Draft created (pending acceptance)" if soft else "Draft created successfully",
        form_state=form_state,
    )
