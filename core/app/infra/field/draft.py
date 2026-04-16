"""Field draft logic — canonical surface over existing draft tools."""

from __future__ import annotations

from typing import Any
from uuid import UUID

import asyncpg
from fastapi import HTTPException
from redis.asyncio import Redis

from app.infra.field.permissions import compute_can_draft
from app.infra.field.refresh import refresh_field_impl
from app.infra.field.types import (
    DraftFormState,
    PatchFieldDraftApiRequest,
    PatchFieldDraftApiResponse,
    SaveFieldFieldError,
)
from app.infra.profile_identity_context import resolve_profile_identity_context
from app.infra.tools.sanitize import sanitize_model_kwargs
from app.tools.entries.field_drafts.create import create_field_draft
from app.tools.resources.conditional_parameters.create import create_conditional_parameter
from app.tools.resources.departments.search import search_departments
from app.tools.resources.descriptions.create import create_description
from app.tools.resources.descriptions.search import search_descriptions
from app.tools.resources.flags.search import search_flags
from app.tools.resources.names.create import create_name
from app.tools.resources.names.search import search_names
from app.tools.resources.parameters.search import search_parameters


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
    request: PatchFieldDraftApiRequest,
) -> list[SaveFieldFieldError]:
    """Resolve raw value fields to resource IDs (mutates request in place)."""

    errors: list[SaveFieldFieldError] = []

    if request.name is not None and request.name_id is None:
        results = await search_names(
            conn,
            redis,
            search=request.name,
            limit_count=20,
            field=True,
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
            field=True,
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
            flag_type="field_active",
            field=True,
        )
        match = next((flag for flag in results if getattr(flag, "type", None) == "field_active"), None)
        if match and match.id:
            resolved_flag_id = match.id
        else:
            errors.append(
                SaveFieldFieldError(
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
            field=True,
        )
        resolved_ids: list[UUID] = []
        for raw_value in request.departments:
            item_id = _exact_match_id(results, raw_value, attr="name")
            if item_id is None:
                errors.append(
                    SaveFieldFieldError(
                        field="departments",
                        message=f'Department "{raw_value}" not found',
                    )
                )
                continue
            resolved_ids.append(item_id)
        if not any(error.field == "departments" for error in errors):
            request.department_ids = _merge_unique(request.department_ids, resolved_ids)

    if request.conditional_parameters:
        results = await search_parameters(
            conn,
            redis,
            search=None,
            limit_count=1000,
            suggest_source="all",
        )
        resolved_ids: list[UUID] = []
        for raw_value in request.conditional_parameters:
            parameter_id = next(
                (
                    item.parameter_id
                    for item in results
                    if isinstance(getattr(item, "name", None), str)
                    and item.parameter_id
                    and item.name.lower() == raw_value.strip().lower()
                ),
                None,
            )
            if parameter_id is None:
                errors.append(
                    SaveFieldFieldError(
                        field="conditional_parameters",
                        message=f'Conditional parameter "{raw_value}" not found',
                    )
                )
                continue
            conditional_parameter = await create_conditional_parameter(
                conn,
                parameter_id,
                redis,
            )
            resolved_ids.append(conditional_parameter.id)
        if not any(error.field == "conditional_parameters" for error in errors):
            request.conditional_parameter_ids = _merge_unique(
                request.conditional_parameter_ids,
                resolved_ids,
            )

    return errors


async def patch_field_draft_impl(
    pool: asyncpg.Pool,
    redis: Redis,
    *,
    profile_id: UUID,
    session_id: UUID,
    request: PatchFieldDraftApiRequest | None = None,
    draft_id: UUID | None = None,
    soft: bool = False,
    accept: bool | None = None,
    idempotency_key: UUID | None = None,
    **kwargs: Any,
) -> PatchFieldDraftApiResponse:
    """Field draft using the canonical request/response contract."""

    if request is None:
        filtered = sanitize_model_kwargs(
            kwargs,
            list_fields={
                "department_ids",
                "departments",
                "conditional_parameter_ids",
                "conditional_parameters",
                "pending_ids",
            },
            bool_fields={"active_flag"},
            value_id_pairs=[
                ("name", "name_id"),
                ("description", "description_id"),
            ],
        )
        if draft_id is not None:
            filtered["draft_id"] = draft_id
            filtered["input_draft_id"] = draft_id
        request = PatchFieldDraftApiRequest(**filtered)

    if draft_id is not None and request.draft_id is None:
        request.draft_id = draft_id
    if draft_id is not None and request.input_draft_id is None:
        request.input_draft_id = draft_id

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
            detail="You don't have permission to create or edit field drafts.",
        )

    if accept is not None and idempotency_key is not None:
        if accept:
            async with pool.acquire() as conn:
                async with conn.transaction():
                    await create_field_draft(
                        conn,
                        session_id=session_id,
                        id=idempotency_key,
                        soft=False,
                        profile_ids=[profile.profiles_id],
                        pending_ids=set(request.pending_ids) if request.pending_ids else None,
                    )
            await refresh_field_impl(
                pool,
                redis,
                profile_id=profile_id,
                session_id=session_id,
                targets=["field_drafts_mv"],
                operation_key=idempotency_key,
            )
        return PatchFieldDraftApiResponse(
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
            result = await create_field_draft(
                conn,
                session_id=session_id,
                id=idempotency_key,
                soft=soft,
                name_ids=[request.name_id] if request.name_id else None,
                description_ids=[request.description_id]
                if request.description_id
                else None,
                flag_ids=[request.flag_id] if request.flag_id else None,
                department_ids=request.department_ids,
                conditional_parameter_ids=request.conditional_parameter_ids,
                profile_ids=[profile.profiles_id],
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
        conditional_parameter_ids=request.conditional_parameter_ids or [],
        pending_ids=request.pending_ids or [],
    )

    if not soft:
        await refresh_field_impl(
            pool,
            redis,
            profile_id=profile_id,
            session_id=session_id,
            targets=["field_drafts_mv"],
            soft=soft,
            operation_key=result.id,
        )

    return PatchFieldDraftApiResponse(
        success=True,
        draft_id=result.id,
        idempotency_key=result.id,
        message="Draft created (pending acceptance)" if soft else "Draft created successfully",
        form_state=form_state,
    )
