"""Auth draft logic — canonical draft-first flow."""

from __future__ import annotations

from uuid import UUID

import asyncpg
from fastapi import HTTPException
from redis.asyncio import Redis

from app.infra.auth.permissions import compute_can_draft
from app.infra.auth.refresh import refresh_auth_impl
from app.infra.auth.types import (
    DraftFormState,
    PatchAuthDraftApiRequest,
    PatchAuthDraftApiResponse,
    SaveAuthFieldError,
)
from app.infra.profile_identity_context import resolve_profile_identity_context
from app.tools.entries.auth_drafts.create import create_auth_draft
from app.tools.entries.auth_drafts.get import get_auth_drafts
from app.tools.resources.departments.search import search_departments
from app.tools.resources.descriptions.create import create_description
from app.tools.resources.descriptions.search import search_descriptions
from app.tools.resources.flags.search import search_flags
from app.tools.resources.names.create import create_name
from app.tools.resources.names.search import search_names
from app.tools.resources.protocols.search import search_protocols
from app.tools.resources.slugs.search import search_slugs

AUTH_ACTIVE_FLAG = "auth_active"


async def _resolve_creatable_values(
    pool: asyncpg.Pool,
    redis: Redis,
    request: PatchAuthDraftApiRequest,
) -> list[SaveAuthFieldError]:
    """Resolve raw auth values to IDs in-place."""
    errors: list[SaveAuthFieldError] = []

    async with pool.acquire() as conn:
        if request.name is not None and request.name_id is None:
            existing = await search_names(conn, redis, search=request.name, limit_count=10, auth=True)
            match = next((item for item in existing if item.name and item.name.lower() == request.name.lower()), None)
            if match and match.id:
                request.name_id = match.id
            else:
                result = await create_name(conn, request.name, redis)
                request.name_id = result.id

        if request.description is not None and request.description_id is None:
            existing = await search_descriptions(conn, redis, search=request.description, limit_count=10, auth=True)
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

    if request.active_flag is not None and request.flag_id is None:
        async with pool.acquire() as conn:
            flags = await search_flags(conn, redis, search=None, limit_count=100, auth=True)
        match = next((flag for flag in flags if getattr(flag, "name", None) == AUTH_ACTIVE_FLAG), None)
        if request.active_flag:
            if match and match.id:
                request.flag_id = match.id
            else:
                errors.append(SaveAuthFieldError(field="active_flag", message="Active auth flag resource not found"))
        else:
            request.flag_id = None

    if request.departments is not None and request.department_ids is None:
        async with pool.acquire() as conn:
            all_departments = await search_departments(conn, redis, search=None, limit_count=1000)
        dept_name_map = {item.name.lower(): item.id for item in all_departments if item.name and item.id}
        resolved_ids: list[UUID] = []
        for department_name in request.departments:
            department_id = dept_name_map.get(department_name.lower())
            if department_id:
                resolved_ids.append(department_id)
            else:
                errors.append(
                    SaveAuthFieldError(
                        field="departments",
                        message=f'Department "{department_name}" not found',
                    )
                )
        if not any(error.field == "departments" for error in errors):
            request.department_ids = resolved_ids

    if request.protocols is not None and request.protocol_ids is None:
        async with pool.acquire() as conn:
            all_protocols = await search_protocols(conn, redis, search=None, limit_count=1000, auth=True)
        protocol_map = {item.value.lower(): item.id for item in all_protocols if item.value and item.id}
        resolved_ids = []
        for value in request.protocols:
            protocol_id = protocol_map.get(value.lower())
            if protocol_id:
                resolved_ids.append(protocol_id)
            else:
                errors.append(
                    SaveAuthFieldError(field="protocols", message=f'Protocol "{value}" not found')
                )
        if not any(error.field == "protocols" for error in errors):
            request.protocol_ids = resolved_ids

    if request.slugs is not None and request.slug_ids is None:
        async with pool.acquire() as conn:
            all_slugs = await search_slugs(conn, redis, search=None, limit_count=1000, auth=True)
        slug_map = {item.value.lower(): item.id for item in all_slugs if item.value and item.id}
        resolved_ids = []
        for value in request.slugs:
            slug_id = slug_map.get(value.lower())
            if slug_id:
                resolved_ids.append(slug_id)
            else:
                errors.append(
                    SaveAuthFieldError(field="slugs", message=f'Slug "{value}" not found')
                )
        if not any(error.field == "slugs" for error in errors):
            request.slug_ids = resolved_ids

    return errors


async def patch_auth_draft_impl(
    pool: asyncpg.Pool,
    redis: Redis,
    *,
    profile_id: UUID,
    session_id: UUID,
    request: PatchAuthDraftApiRequest,
    soft: bool = False,
    accept: bool | None = None,
    idempotency_key: UUID | None = None,
) -> PatchAuthDraftApiResponse:
    """Persist canonical auth draft state and return server-authored form state."""

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
        raise HTTPException(status_code=401, detail="Profile not found. Please sign in again.")

    if not compute_can_draft(role_level=profile.role_level, role_permissions=profile.role_permissions):
        raise HTTPException(status_code=403, detail="You don't have permission to create or edit auth drafts.")

    if accept is not None and idempotency_key is not None:
        if accept:
            async with pool.acquire() as conn:
                drafts = await get_auth_drafts(conn, [idempotency_key])
                if drafts:
                    draft = drafts[0]
                    async with conn.transaction():
                        await create_auth_draft(
                            conn,
                            session_id=session_id,
                            id=idempotency_key,
                            soft=False,
                            department_ids=draft.department_ids,
                            description_ids=draft.description_ids,
                            flag_ids=draft.flag_ids,
                            item_ids=draft.item_ids,
                            name_ids=draft.name_ids,
                            profile_ids=draft.profile_ids or [profile.profiles_id],
                            protocol_ids=draft.protocol_ids,
                            slug_ids=draft.slug_ids,
                            pending_ids=set(),
                        )
            await refresh_auth_impl(pool, redis, profile_id=profile_id)

        return PatchAuthDraftApiResponse(
            success=True,
            draft_id=idempotency_key,
            idempotency_key=idempotency_key,
            message="Draft accepted" if accept else "Draft rejected",
            form_state=DraftFormState(),
        )

    errors = await _resolve_creatable_values(pool, redis, request)
    if errors:
        raise HTTPException(status_code=400, detail=[error.model_dump() for error in errors])

    pending_ids = set(request.pending_ids or [])
    target_draft_id = resolved_draft_id or idempotency_key

    async with pool.acquire() as conn:
        async with conn.transaction():
            result = await create_auth_draft(
                conn,
                session_id=session_id,
                id=target_draft_id,
                soft=soft,
                department_ids=request.department_ids,
                description_ids=[request.description_id] if request.description_id else None,
                flag_ids=[request.flag_id] if request.flag_id else None,
                item_ids=request.item_ids,
                name_ids=[request.name_id] if request.name_id else None,
                profile_ids=[profile.profiles_id],
                protocol_ids=request.protocol_ids,
                slug_ids=request.slug_ids,
                pending_ids=pending_ids,
            )

    form_state = DraftFormState(
        name=request.name,
        name_id=request.name_id,
        description=request.description,
        description_id=request.description_id,
        flag_id=request.flag_id,
        department_ids=request.department_ids or [],
        protocol_ids=request.protocol_ids or [],
        slug_ids=request.slug_ids or [],
        item_ids=request.item_ids or [],
        pending_ids=list(pending_ids),
    )

    if not soft:
        await refresh_auth_impl(pool, redis, profile_id=profile_id)

    return PatchAuthDraftApiResponse(
        success=True,
        draft_id=result.id,
        idempotency_key=result.id,
        message="Draft saved successfully",
        form_state=form_state,
    )
