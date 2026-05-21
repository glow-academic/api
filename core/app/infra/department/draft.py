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
from app.tools.entries.department_drafts.get import get_department_drafts
from app.tools.entries.soft_calls.create import create_soft_call
from app.tools.entries.soft_calls.get import get_soft_call
from app.tools.entries.soft_calls.refresh import refresh_soft_calls
from app.tools.entries.soft_calls.search import search_soft_calls
from app.tools.resources.descriptions.create import create_description
from app.tools.resources.descriptions.search import search_descriptions
from app.tools.resources.flags.search import search_flags
from app.tools.resources.names.create import create_name
from app.tools.resources.names.search import search_names
from app.tools.resources.settings.search import search_settings

ARTIFACT = "department"
OPERATION = "draft"


async def _maybe_auto_accept_department_draft(
    pool: asyncpg.Pool,
    redis: Redis,
    *,
    draft_id: UUID,
    session_id: UUID,
    profile_ids: list[UUID],
) -> bool:
    """Auto-accept a department draft when no pending fields remain."""
    async with pool.acquire() as conn:
        ledger_entries = await search_soft_calls(
            conn,
            redis,
            artifact=ARTIFACT,
            operation=OPERATION,
            artifact_ids=[draft_id],
            status="pending",
            limit=1,
        )
    if not ledger_entries:
        return False
    call_id = ledger_entries[0].call_id

    async with pool.acquire() as conn:
        drafts = await get_department_drafts(conn, [draft_id], active=None)
    if not drafts:
        return False
    draft = drafts[0]
    if (
        draft.pending_description_ids
        or draft.pending_flag_ids
        or draft.pending_name_ids
        or draft.pending_setting_ids
    ):
        return False

    async with pool.acquire() as conn:
        async with conn.transaction():
            await create_department_draft(
                conn,
                session_id=session_id,
                id=draft_id,
                soft=False,
                name_ids=draft.name_ids,
                description_ids=draft.description_ids,
                flag_ids=draft.flag_ids,
                setting_ids=draft.setting_ids,
                profile_ids=draft.profile_ids or profile_ids,
                pending_ids=set(),
            )
            await create_soft_call(
                conn,
                redis,
                call_id=call_id,
                artifact=ARTIFACT,
                operation=OPERATION,
                artifact_id=draft_id,
                status="accepted",
            )
    async with pool.acquire() as conn:
        await refresh_soft_calls(conn)
    return True


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

    # Resolve denormalized flag booleans to canonical flag_ids via (type, value)
    # lookup in flags_resource. Explicit flag_ids are retained verbatim; the
    # derived id is merged in so both forms coexist without conflict.
    denorm_flag_values: dict[str, bool] = {}
    if request.active is not None:
        denorm_flag_values["department_active"] = bool(request.active)
    if denorm_flag_values:
        all_flags = await search_flags(
            conn,
            redis,
            search=None,
            limit_count=200,
            bypass_cache=True,
        )
        resolved_flag_ids: list[UUID] = list(request.flag_ids or [])
        resolved_seen = set(resolved_flag_ids)
        for flag_type, desired_value in denorm_flag_values.items():
            match = next(
                (
                    f
                    for f in all_flags
                    if (getattr(f, "type", None) == flag_type
                        or getattr(f, "name", None) == flag_type)
                    and getattr(f, "value", None) is desired_value
                ),
                None,
            )
            if match and match.id and match.id not in resolved_seen:
                resolved_flag_ids.append(match.id)
                resolved_seen.add(match.id)
            elif not match:
                errors.append(
                    SaveDepartmentFieldError(
                        field=flag_type,
                        message=(
                            f"Flag row not found for type={flag_type} "
                            f"value={desired_value}"
                        ),
                    )
                )
        request.flag_ids = resolved_flag_ids

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
        async with pool.acquire() as conn:
            entry = await get_soft_call(conn, idempotency_key, redis, artifact=ARTIFACT)
        if entry is None or entry.status != "pending" or entry.operation != OPERATION:
            raise HTTPException(
                status_code=404,
                detail="No pending department draft for this call.",
            )
        target_id = entry.artifact_id

        if accept:
            async with pool.acquire() as conn:
                drafts = await get_department_drafts(conn, [target_id], active=None)
                async with conn.transaction():
                    if drafts:
                        draft = drafts[0]
                        await create_department_draft(
                            conn,
                            session_id=session_id,
                            id=target_id,
                            soft=False,
                            name_ids=draft.name_ids,
                            description_ids=draft.description_ids,
                            flag_ids=draft.flag_ids,
                            setting_ids=draft.setting_ids,
                            profile_ids=draft.profile_ids or [profile.profiles_id],
                            pending_ids=set(),
                        )
                    else:
                        await create_department_draft(
                            conn,
                            session_id=session_id,
                            id=target_id,
                            soft=False,
                            profile_ids=[profile.profiles_id],
                        )

        async with pool.acquire() as conn:
            await create_soft_call(
                conn,
                redis,
                call_id=idempotency_key,
                artifact=ARTIFACT,
                operation=OPERATION,
                artifact_id=target_id,
                status="accepted" if accept else "rejected",
            )
        async with pool.acquire() as conn:
            await refresh_soft_calls(conn)

        await refresh_department_impl(
            pool,
            redis,
            profile_id=profile_id,
            session_id=session_id,
            targets=["department_drafts_mv"],
            operation_key=idempotency_key,
        )
        return PatchDepartmentDraftApiResponse(
            success=True,
            draft_id=target_id,
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
                name=request.name or "",
                name_ids=[request.name_id] if request.name_id else None,
                description_ids=[request.description_id] if request.description_id else None,
                flag_ids=request.flag_ids or None,
                setting_ids=request.setting_ids,
                profile_ids=[profile.profiles_id],
                pending_ids=set(request.pending_ids) if request.pending_ids else None,
            )

            if soft and idempotency_key is not None:
                await create_soft_call(
                    conn,
                    redis,
                    call_id=idempotency_key,
                    artifact=ARTIFACT,
                    operation=OPERATION,
                    artifact_id=result.id,
                )

    if soft and idempotency_key is not None:
        async with pool.acquire() as conn:
            await refresh_soft_calls(conn)

    if not soft:
        await _maybe_auto_accept_department_draft(
            pool, redis,
            draft_id=result.id,
            session_id=session_id,
            profile_ids=[profile.profiles_id],
        )

    # Re-derive denormalized flag booleans from the final flag_ids so the client
    # echo matches whatever the server actually persisted.
    echoed_active: bool | None = request.active
    if request.flag_ids:
        async with pool.acquire() as conn:
            flag_rows = await search_flags(
                conn,
                redis,
                search=None,
                limit_count=200,
                bypass_cache=True,
            )
        rows_by_id = {row.id: row for row in flag_rows if getattr(row, "id", None)}
        for fid in request.flag_ids:
            row = rows_by_id.get(fid)
            if not row:
                continue
            rtype = getattr(row, "type", None) or getattr(row, "name", None)
            rval = getattr(row, "value", None)
            if rtype == "department_active":
                echoed_active = rval

    form_state = DraftFormState(
        name_id=request.name_id,
        name=request.name,
        description_id=request.description_id,
        description=request.description,
        flag_ids=request.flag_ids or [],
        active=echoed_active,
        setting_ids=request.setting_ids or [],
        pending_ids=request.pending_ids or [],
    )

    if not soft:
        await refresh_department_impl(
            pool,
            redis,
            profile_id=profile_id,
            session_id=session_id,
            targets=["department_drafts_mv"],
            operation_key=result.id,
        )

    return PatchDepartmentDraftApiResponse(
        success=True,
        draft_id=result.id,
        idempotency_key=result.id,
        message="Draft created (pending acceptance)" if soft else "Draft created successfully",
        form_state=form_state,
    )
