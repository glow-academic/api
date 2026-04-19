"""Setting draft logic — canonical draft-first flow."""

from __future__ import annotations

from uuid import UUID

import asyncpg
from fastapi import HTTPException
from redis.asyncio import Redis

from app.infra.profile_identity_context import resolve_profile_identity_context
from app.infra.setting.permissions import compute_can_draft
from app.infra.setting.refresh import refresh_setting_impl
from app.infra.setting.types import (
    DraftFormState,
    PatchSettingDraftApiRequest,
    PatchSettingDraftApiResponse,
    SaveSettingFieldError,
)
from app.tools.entries.setting_drafts.create import create_setting_draft
from app.tools.entries.setting_drafts.get import get_setting_drafts
from app.tools.resources.departments.search import search_departments
from app.tools.resources.descriptions.create import create_description
from app.tools.resources.descriptions.get import get_descriptions
from app.tools.resources.descriptions.search import search_descriptions
from app.tools.resources.flags.search import search_flags
from app.tools.resources.names.create import create_name
from app.tools.resources.names.get import get_names
from app.tools.resources.names.search import search_names

SETTING_ACTIVE_FLAG = "setting_active"


async def _resolve_creatable_values(
    pool: asyncpg.Pool,
    redis: Redis,
    request: PatchSettingDraftApiRequest,
) -> list[SaveSettingFieldError]:
    """Resolve raw values to IDs, mutating request in place."""

    errors: list[SaveSettingFieldError] = []
    request.active_flag_id = request.active_flag_id or request.flag_id

    async with pool.acquire() as conn:
        if request.name is not None and request.name_id is None:
            existing = await search_names(
                conn,
                redis,
                search=request.name,
                limit_count=10,
                setting=True,
            )
            match = next(
                (
                    item
                    for item in existing
                    if item.name and item.name.lower() == request.name.lower()
                ),
                None,
            )
            if match and match.id:
                request.name_id = match.id
            else:
                created = await create_name(conn, request.name, redis)
                request.name_id = created.id

        if request.description is not None and request.description_id is None:
            existing = await search_descriptions(
                conn,
                redis,
                search=request.description,
                limit_count=10,
                setting=True,
            )
            match = next(
                (
                    item
                    for item in existing
                    if item.description
                    and item.description.lower() == request.description.lower()
                ),
                None,
            )
            if match and match.id:
                request.description_id = match.id
            else:
                created = await create_description(conn, request.description, redis)
                request.description_id = created.id

    if request.active_flag is not None and request.active_flag_id is None:
        async with pool.acquire() as conn:
            flags = await search_flags(
                conn,
                redis,
                search=None,
                limit_count=100,
                setting=True,
            )
        match = next(
            (
                flag
                for flag in flags
                if getattr(flag, "name", None) == SETTING_ACTIVE_FLAG
                or getattr(flag, "type", None) == SETTING_ACTIVE_FLAG
            ),
            None,
        )
        if request.active_flag:
            if match and match.id:
                request.active_flag_id = match.id
            else:
                errors.append(
                    SaveSettingFieldError(
                        field="active_flag",
                        message="Active setting flag resource not found",
                    )
                )
        else:
            request.active_flag_id = None

    if request.departments is not None and request.department_ids is None:
        async with pool.acquire() as conn:
            all_departments = await search_departments(
                conn,
                redis,
                search=None,
                limit_count=1000,
            )
        department_name_map = {
            item.name.lower(): item.id
            for item in all_departments
            if item.name and item.id
        }
        resolved_ids: list[UUID] = []
        for department_name in request.departments:
            department_id = department_name_map.get(department_name.lower())
            if department_id:
                resolved_ids.append(department_id)
            else:
                errors.append(
                    SaveSettingFieldError(
                        field="departments",
                        message=f'Department "{department_name}" not found',
                    )
                )
        if not any(error.field == "departments" for error in errors):
            request.department_ids = resolved_ids

    request.flag_id = request.active_flag_id
    return errors


async def patch_setting_draft_impl(
    pool: asyncpg.Pool,
    redis: Redis,
    *,
    profile_id: UUID,
    session_id: UUID,
    request: PatchSettingDraftApiRequest,
    soft: bool = False,
    accept: bool | None = None,
    idempotency_key: UUID | None = None,
) -> PatchSettingDraftApiResponse:
    """Persist canonical setting draft state and return server-authored form state."""

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

    if not compute_can_draft(
        role_level=profile.role_level,
        role_permissions=profile.role_permissions,
    ):
        raise HTTPException(
            status_code=403,
            detail="You don't have permission to create or edit setting drafts.",
        )

    if accept is not None and idempotency_key is not None:
        if accept:
            async with pool.acquire() as conn:
                drafts = await get_setting_drafts(conn, [idempotency_key])
                if drafts:
                    draft = drafts[0]
                    async with conn.transaction():
                        await create_setting_draft(
                            conn,
                            session_id=session_id,
                            id=idempotency_key,
                            soft=False,
                            agent_ids=draft.agent_ids,
                            auth_item_key_ids=draft.auth_item_key_ids,
                            auth_ids=draft.auth_ids,
                            color_ids=draft.color_ids,
                            department_ids=draft.department_ids,
                            description_ids=draft.description_ids,
                            flag_ids=draft.flag_ids,
                            item_ids=draft.item_ids,
                            name_ids=draft.name_ids,
                            profile_ids=draft.profile_ids or [profile.profiles_id],
                            provider_key_ids=draft.provider_key_ids,
                            threshold_ids=draft.threshold_ids,
                            pending_ids=set(),
                        )
            await refresh_setting_impl(
                pool,
                redis,
                profile_id=profile_id,
            )

        return PatchSettingDraftApiResponse(
            success=True,
            draft_id=idempotency_key,
            idempotency_key=idempotency_key,
            message="Draft accepted" if accept else "Draft rejected",
            form_state=DraftFormState(),
        )

    errors = await _resolve_creatable_values(pool, redis, request)
    if errors:
        raise HTTPException(
            status_code=400,
            detail=[error.model_dump() for error in errors],
        )

    pending_ids = set(request.pending_ids or [])
    target_draft_id = resolved_draft_id or idempotency_key
    draft_profile_ids = list(
        dict.fromkeys(
            [profile.profiles_id] + list(request.profile_ids or [])
        )
    )

    async with pool.acquire() as conn:
        async with conn.transaction():
            result = await create_setting_draft(
                conn,
                session_id=session_id,
                id=target_draft_id,
                soft=soft,
                agent_ids=request.agent_ids,
                auth_item_key_ids=request.auth_item_key_ids,
                auth_ids=request.auth_ids,
                color_ids=request.color_ids,
                department_ids=request.department_ids,
                description_ids=[request.description_id] if request.description_id else None,
                flag_ids=[request.active_flag_id] if request.active_flag_id else None,
                name_ids=[request.name_id] if request.name_id else None,
                profile_ids=draft_profile_ids,
                provider_key_ids=request.provider_key_ids,
                pending_ids=pending_ids,
            )

    resolved_name = request.name
    if request.name_id and resolved_name is None:
        async with pool.acquire() as conn:
            names = await get_names(conn, [request.name_id], redis)
        resolved_name = names[0].name if names else None

    resolved_description = request.description
    if request.description_id and resolved_description is None:
        async with pool.acquire() as conn:
            descriptions = await get_descriptions(conn, [request.description_id], redis)
        resolved_description = descriptions[0].description if descriptions else None

    form_state = DraftFormState(
        name_id=request.name_id,
        name=resolved_name,
        description_id=request.description_id,
        description=resolved_description,
        active_flag_id=request.active_flag_id,
        flag_id=request.active_flag_id,
        department_ids=request.department_ids or [],
        color_ids=request.color_ids or [],
        profile_ids=request.profile_ids or [],
        auth_ids=request.auth_ids or [],
        provider_key_ids=request.provider_key_ids or [],
        auth_item_key_ids=request.auth_item_key_ids or [],
        agent_ids=request.agent_ids or [],
        pending_ids=sorted(pending_ids),
    )

    if not soft:
        await refresh_setting_impl(
            pool,
            redis,
            profile_id=profile_id,
        )

    return PatchSettingDraftApiResponse(
        success=True,
        draft_id=result.id,
        idempotency_key=idempotency_key or result.id,
        message="Draft saved successfully",
        form_state=form_state,
    )
