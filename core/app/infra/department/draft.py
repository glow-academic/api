"""Department draft logic — canonical surface over existing draft tools."""

from __future__ import annotations

from typing import Any
from uuid import UUID

import asyncpg
from fastapi import HTTPException
from redis.asyncio import Redis

from app.infra.department.permissions import compute_can_draft
from app.infra.department.refresh import refresh_department_impl
from app.infra.department.types import (
    DraftFormState,
    PatchDepartmentDraftApiRequest,
    PatchDepartmentDraftApiResponse,
    SaveDepartmentFieldError,
)
from app.infra.profile_identity_context import resolve_profile_identity_context
from app.tools.entries.department_drafts.create import create_department_draft
from app.tools.resources.descriptions.create import create_description
from app.tools.resources.descriptions.search import search_descriptions
from app.tools.resources.flags.search import search_flags
from app.tools.resources.names.create import create_name
from app.tools.resources.names.search import search_names
from app.tools.resources.settings.search import search_settings


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
    request: PatchDepartmentDraftApiRequest,
) -> list[SaveDepartmentFieldError]:
    """Resolve raw value fields to resource IDs (mutates request in place)."""

    errors: list[SaveDepartmentFieldError] = []

    if request.name is not None and request.name_id is None:
        results = await search_names(
            conn,
            redis,
            search=request.name,
            limit_count=20,
            department=True,
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
            department=True,
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
            flag_type="department_active",
            department=True,
        )
        match = next(
            (
                flag
                for flag in results
                if getattr(flag, "type", None) == "department_active"
                or getattr(flag, "name", None) == "department_active"
            ),
            None,
        )
        if match and match.id:
            resolved_flag_id = match.id
        else:
            errors.append(
                SaveDepartmentFieldError(
                    field="active_flag",
                    message="Active flag resource not found",
                )
            )
    if resolved_flag_id is not None:
        request.flag_id = resolved_flag_id
        request.active_flag_id = resolved_flag_id

    if request.settings:
        results = await search_settings(
            conn,
            redis,
            search=None,
            limit_count=1000,
            department=True,
        )
        resolved_ids: list[UUID] = []
        for raw_value in request.settings:
            item_id = _exact_match_id(results, raw_value, attr="name")
            if item_id is None:
                errors.append(
                    SaveDepartmentFieldError(
                        field="settings",
                        message=f'Setting "{raw_value}" not found',
                    )
                )
                continue
            resolved_ids.append(item_id)
        if not any(error.field == "settings" for error in errors):
            request.setting_ids = _merge_unique(request.setting_ids, resolved_ids)

    return errors


async def patch_department_draft_impl(
    pool: asyncpg.Pool,
    redis: Redis,
    *,
    profile_id: UUID,
    session_id: UUID,
    request: PatchDepartmentDraftApiRequest | None = None,
    draft_id: UUID | None = None,
    soft: bool = False,
    accept: bool | None = None,
    idempotency_key: UUID | None = None,
    **kwargs: Any,
) -> PatchDepartmentDraftApiResponse:
    """Department draft using the canonical request/response contract."""

    if request is None:
        request = PatchDepartmentDraftApiRequest(**kwargs)

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
            detail="You don't have permission to create or edit department drafts.",
        )

    if accept is not None and idempotency_key is not None:
        if accept:
            async with pool.acquire() as conn:
                async with conn.transaction():
                    await create_department_draft(
                        conn,
                        session_id=session_id,
                        id=idempotency_key,
                        soft=False,
                        profile_ids=[profile.profiles_id],
                        pending_ids=set(request.pending_ids) if request.pending_ids else None,
                    )
            await refresh_department_impl(pool, redis, profile_id=profile_id)
        return PatchDepartmentDraftApiResponse(
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
            result = await create_department_draft(
                conn,
                session_id=session_id,
                id=idempotency_key,
                soft=soft,
                name_ids=[request.name_id] if request.name_id else None,
                description_ids=[request.description_id] if request.description_id else None,
                flag_ids=[request.flag_id] if request.flag_id else None,
                setting_ids=request.setting_ids,
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
        setting_ids=request.setting_ids or [],
        pending_ids=request.pending_ids or [],
    )

    if not soft:
        await refresh_department_impl(pool, redis, profile_id=profile_id)

    return PatchDepartmentDraftApiResponse(
        success=True,
        draft_id=result.id,
        idempotency_key=result.id,
        message="Draft saved successfully",
        form_state=form_state,
    )
