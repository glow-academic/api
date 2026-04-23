"""Rubric draft logic — canonical surface over existing draft tools."""

from __future__ import annotations

from typing import Any
from uuid import UUID

import asyncpg
from fastapi import HTTPException
from redis.asyncio import Redis

from app.infra.profile_identity_context import resolve_profile_identity_context
from app.infra.rubric.permissions import compute_can_draft
from app.infra.rubric.refresh import refresh_rubric_impl
from app.infra.rubric.types import (
    DraftFormState,
    PatchRubricDraftApiRequest,
    PatchRubricDraftApiResponse,
    SaveRubricFieldError,
)
from app.tools.entries.rubric_drafts.create import create_rubric_draft
from app.tools.entries.rubric_drafts.get import get_rubric_drafts
from app.tools.resources.departments.search import search_departments
from app.tools.resources.descriptions.create import create_description
from app.tools.resources.descriptions.search import search_descriptions
from app.tools.resources.flags.search import search_flags
from app.tools.resources.names.create import create_name
from app.tools.resources.names.search import search_names
from app.tools.resources.standards.create import create_standard


def _exact_match_id(results: list[Any], raw_value: str, *, attr: str = "name") -> UUID | None:
    needle = raw_value.strip().lower()
    for item in results:
        value = getattr(item, attr, None)
        item_id = getattr(item, "id", None)
        if isinstance(value, str) and item_id and value.lower() == needle:
            return item_id
    return None


def _merge_unique(existing: list[UUID] | None, new_ids: list[UUID]) -> list[UUID]:
    merged = list(existing or [])
    seen = set(merged)
    for item_id in new_ids:
        if item_id not in seen:
            seen.add(item_id)
            merged.append(item_id)
    return merged


async def _resolve_creatable_values(
    conn: asyncpg.Connection,
    redis: Redis,
    request: PatchRubricDraftApiRequest,
    *,
    profile_department_ids: list[UUID] | None,
) -> list[SaveRubricFieldError]:
    """Resolve raw value fields to resource IDs (mutates request in place)."""

    errors: list[SaveRubricFieldError] = []

    if request.name is not None and request.name_id is None:
        results = await search_names(
            conn,
            redis,
            search=request.name,
            limit_count=20,
            rubric=True,
        )
        match_id = _exact_match_id(results, request.name)
        if match_id is None:
            match_id = (await create_name(conn, request.name, redis)).id
        request.name_id = match_id

    if request.description is not None and request.description_id is None:
        results = await search_descriptions(
            conn,
            redis,
            search=request.description,
            limit_count=20,
            rubric=True,
        )
        match_id = _exact_match_id(results, request.description, attr="description")
        if match_id is None:
            match_id = (await create_description(conn, request.description, redis)).id
        request.description_id = match_id

    resolved_flag_id = request.active_flag_id or request.flag_id
    if request.active_flag is not None and resolved_flag_id is None and request.active_flag:
        results = await search_flags(
            conn,
            redis,
            search=None,
            limit_count=1000,
            rubric=True,
        )
        match = next(
            (
                flag
                for flag in results
                if getattr(flag, "type", None) == "rubric_active"
                or getattr(flag, "name", None) == "rubric_active"
            ),
            None,
        )
        if match and match.id:
            resolved_flag_id = match.id
        else:
            errors.append(
                SaveRubricFieldError(
                    field="active_flag",
                    message="Active flag resource not found",
                )
            )
    if resolved_flag_id is not None:
        request.flag_id = resolved_flag_id
        request.active_flag_id = resolved_flag_id

    if request.departments:
        results = await search_departments(
            conn,
            redis,
            search=None,
            limit_count=1000,
            offset_count=0,
            department_ids=profile_department_ids or [],
            suggest_source="all",
        )
        resolved_ids: list[UUID] = []
        for raw_value in request.departments:
            item_id = _exact_match_id(results, raw_value, attr="name")
            if item_id is None:
                errors.append(
                    SaveRubricFieldError(
                        field="departments",
                        message=f'Department "{raw_value}" not found',
                    )
                )
                continue
            resolved_ids.append(item_id)
        if not any(error.field == "departments" for error in errors):
            request.department_ids = _merge_unique(request.department_ids, resolved_ids)

    # Grid-editor standards: entries without id are created here; resulting
    # ids merge into request.standard_ids so the downstream draft row sees a
    # single flat list. The returned value list retains every entry with its
    # filled-in id so the client can replace stale ids in its local grid.
    if request.standards:
        resolved_standard_ids: list[UUID] = []
        for value in request.standards:
            if value.id is None:
                created = await create_standard(
                    conn,
                    name=value.name,
                    description=value.description or "",
                    points=value.points,
                    standard_group_id=value.standard_group_id,
                    redis=redis,
                )
                if created.id is None:
                    errors.append(
                        SaveRubricFieldError(
                            field="standards",
                            message=f'Failed to create standard "{value.name}"',
                        )
                    )
                    continue
                value.id = created.id
            resolved_standard_ids.append(value.id)
        request.standard_ids = _merge_unique(request.standard_ids, resolved_standard_ids)

    return errors


async def patch_rubric_draft_impl(
    pool: asyncpg.Pool,
    redis: Redis,
    *,
    profile_id: UUID,
    session_id: UUID,
    request: PatchRubricDraftApiRequest | None = None,
    draft_id: UUID | None = None,
    soft: bool = False,
    accept: bool | None = None,
    idempotency_key: UUID | None = None,
    **kwargs: Any,
) -> PatchRubricDraftApiResponse:
    """Rubric draft using the canonical request/response contract."""

    if request is None:
        request = PatchRubricDraftApiRequest(**kwargs)

    request.draft_id = request.draft_id or request.input_draft_id or draft_id
    request.input_draft_id = request.input_draft_id or request.draft_id

    idempotency_key = idempotency_key or request.idempotency_key
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
            detail="You don't have permission to create or edit rubric drafts.",
        )

    if accept is not None and idempotency_key is not None:
        if accept:
            async with pool.acquire() as conn:
                drafts = await get_rubric_drafts(conn, [idempotency_key])
                async with conn.transaction():
                    if drafts:
                        draft = drafts[0]
                        await create_rubric_draft(
                            conn,
                            session_id=session_id,
                            id=idempotency_key,
                            soft=False,
                            name_ids=draft.name_ids,
                            description_ids=draft.description_ids,
                            flag_ids=draft.flag_ids,
                            department_ids=draft.department_ids,
                            point_ids=draft.point_ids,
                            standard_group_ids=draft.standard_group_ids,
                            standard_ids=draft.standard_ids,
                            profile_ids=draft.profile_ids or [profile.profiles_id],
                            pending_ids=set(),
                        )
                    else:
                        await create_rubric_draft(
                            conn,
                            session_id=session_id,
                            id=idempotency_key,
                            soft=False,
                            profile_ids=[profile.profiles_id],
                        )
            await refresh_rubric_impl(
                pool,
                redis,
                profile_id=profile_id,
                session_id=session_id,
                targets=["rubric_drafts_mv"],
                operation_key=idempotency_key,
            )
        return PatchRubricDraftApiResponse(
            success=True,
            draft_id=idempotency_key,
            idempotency_key=idempotency_key,
            message="Draft accepted" if accept else "Draft rejected",
            form_state=DraftFormState(),
        )

    async with pool.acquire() as conn:
        errors = await _resolve_creatable_values(
            conn,
            redis,
            request,
            profile_department_ids=profile.department_ids,
        )
    if errors:
        raise HTTPException(
            status_code=400,
            detail=[error.model_dump() for error in errors],
        )

    async with pool.acquire() as conn:
        async with conn.transaction():
            result = await create_rubric_draft(
                conn,
                session_id=session_id,
                id=idempotency_key,
                soft=soft,
                profile_ids=[profile.profiles_id],
                name_ids=[request.name_id] if request.name_id else None,
                description_ids=[request.description_id] if request.description_id else None,
                flag_ids=[request.flag_id] if request.flag_id else None,
                department_ids=request.department_ids,
                point_ids=request.point_ids,
                standard_group_ids=request.standard_group_ids,
                standard_ids=request.standard_ids,
                pending_ids=set(request.pending_ids) if request.pending_ids else None,
            )

    resolved_flag_id = request.active_flag_id or request.flag_id
    form_state = DraftFormState(
        name_id=request.name_id,
        name=request.name,
        description_id=request.description_id,
        description=request.description,
        flag_id=resolved_flag_id,
        active_flag_id=resolved_flag_id,
        department_ids=request.department_ids or [],
        point_ids=request.point_ids or [],
        standard_group_ids=request.standard_group_ids or [],
        standard_ids=request.standard_ids or [],
        standards=request.standards or [],
        pending_ids=request.pending_ids or [],
    )

    if not soft:
        await refresh_rubric_impl(
            pool,
            redis,
            profile_id=profile_id,
            session_id=session_id,
            targets=["rubric_drafts_mv"],
            operation_key=result.id,
        )

    return PatchRubricDraftApiResponse(
        success=True,
        draft_id=result.id,
        idempotency_key=result.id,
        message="Draft created (pending acceptance)" if soft else "Draft created successfully",
        form_state=form_state,
    )
