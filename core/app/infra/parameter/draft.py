"""Parameter draft logic — canonical surface over existing draft tools."""

from __future__ import annotations

from typing import Any
from uuid import UUID

import asyncpg
from fastapi import HTTPException
from redis.asyncio import Redis

from app.infra.drafts.ownership import enforce_draft_owner
from app.infra.parameter.permissions import compute_can_draft
from app.infra.parameter.refresh import refresh_parameter_impl
from app.infra.parameter.types import (
    DraftFormState,
    PatchParameterDraftApiRequest,
    PatchParameterDraftApiResponse,
    SaveParameterFieldError,
)
from app.infra.profile_identity_context import resolve_profile_identity_context
from app.infra.server_timing import timed
from app.infra.tools.sanitize import sanitize_model_kwargs
from app.tools.entries.parameter_drafts.create import create_parameter_draft
from app.tools.entries.parameter_drafts.get import get_parameter_drafts
from app.tools.entries.soft_calls.create import create_soft_call
from app.tools.entries.soft_calls.get import get_soft_call
from app.tools.entries.soft_calls.refresh import refresh_soft_calls
from app.tools.entries.soft_calls.search import search_soft_calls
from app.tools.resources.departments.search import search_departments

ARTIFACT = "parameter"
OPERATION = "draft"
from app.tools.resources.descriptions.create import create_description
from app.tools.resources.descriptions.search import search_descriptions
from app.tools.resources.fields.get import get_fields
from app.tools.resources.names.create import create_name
from app.tools.resources.names.search import search_names
from app.tools.resources.parameter_fields.search import search_parameter_fields
from app.utils.cache.hedged_row import transaction_with_writeback


def _exact_match_id(results: list[Any], raw_value: str, *, attr: str = "name") -> UUID | None:
    needle = raw_value.strip().lower()
    for item in results:
        value = getattr(item, attr, None)
        item_id = getattr(item, "id", None)
        if isinstance(value, str) and item_id and value.lower() == needle:
            return item_id
    return None


def _merge_unique(existing: list[UUID] | None, new_ids: list[UUID]) -> list[UUID]:
    merged: list[UUID] = list(existing or [])
    seen = set(merged)
    for item_id in new_ids:
        if item_id not in seen:
            seen.add(item_id)
            merged.append(item_id)
    return merged


async def _resolve_parameter_field_ids(
    conn: asyncpg.Connection,
    redis: Redis,
    raw_values: list[str],
) -> tuple[list[UUID] | None, list[SaveParameterFieldError]]:
    results = await search_parameter_fields(
        conn,
        redis,
        limit_count=1000,
    )
    field_ids = [item.field_id for item in results if getattr(item, "field_id", None)]
    fields = await get_fields(conn, field_ids, redis, bypass_cache=False) if field_ids else []
    name_to_resource_id: dict[str, UUID] = {}
    field_lookup = {field.id: field for field in fields if getattr(field, "id", None)}

    for item in results:
        field = field_lookup.get(getattr(item, "field_id", None))
        if field is None or not getattr(item, "id", None):
            continue
        field_name = getattr(field, "name", None)
        if isinstance(field_name, str):
            name_to_resource_id.setdefault(field_name.strip().lower(), item.id)

    resolved_ids: list[UUID] = []
    errors: list[SaveParameterFieldError] = []
    for raw_value in raw_values:
        item_id = name_to_resource_id.get(raw_value.strip().lower())
        if item_id is None:
            errors.append(
                SaveParameterFieldError(
                    field="parameter_fields",
                    message=f'Parameter field "{raw_value}" not found',
                )
            )
            continue
        resolved_ids.append(item_id)

    if errors:
        return None, errors
    return resolved_ids, []


async def _resolve_creatable_values(
    conn: asyncpg.Connection,
    redis: Redis,
    request: PatchParameterDraftApiRequest,
) -> list[SaveParameterFieldError]:
    """Resolve raw value fields to resource IDs (mutates request in place)."""

    errors: list[SaveParameterFieldError] = []

    if request.name is not None and request.name_id is None:
        results = await search_names(
            conn,
            redis,
            search=request.name,
            limit_count=20,
            parameter=True,
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
            parameter=True,
        )
        match_id = _exact_match_id(results, request.description, attr="description")
        if match_id is None:
            match_id = (await create_description(conn, request.description, redis)).id
        request.description_id = match_id

    if request.departments:
        results = await search_departments(
            conn,
            redis,
            search=None,
            limit_count=1000,
            parameter=True,
        )
        resolved_ids: list[UUID] = []
        for raw_value in request.departments:
            item_id = _exact_match_id(results, raw_value, attr="name")
            if item_id is None:
                errors.append(
                    SaveParameterFieldError(
                        field="departments",
                        message=f'Department "{raw_value}" not found',
                    )
                )
                continue
            resolved_ids.append(item_id)
        if not errors:
            request.department_ids = _merge_unique(request.department_ids, resolved_ids)

    if request.parameter_fields:
        resolved_ids, field_errors = await _resolve_parameter_field_ids(
            conn,
            redis,
            request.parameter_fields,
        )
        errors.extend(field_errors)
        if resolved_ids is not None:
            request.field_ids = _merge_unique(request.field_ids, resolved_ids)

    return errors


async def _maybe_auto_accept_parameter_draft(
    pool: asyncpg.Pool,
    redis: Redis,
    *,
    draft_id: UUID,
    session_id: UUID,
    profile_ids: list[UUID],
) -> bool:
    """Auto-accept a draft when no pending fields remain. Mirrors persona."""
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
        drafts = await get_parameter_drafts(conn, [draft_id], redis, active=None)
    if not drafts:
        return False
    draft = drafts[0]
    if (
        draft.pending_department_ids
        or draft.pending_description_ids
        or draft.pending_field_ids
        or draft.pending_flag_ids
        or draft.pending_name_ids
    ):
        return False

    async with pool.acquire() as conn:
        async with transaction_with_writeback(conn):
            await create_parameter_draft(
                conn,
                redis, session_id=session_id,
                id=draft_id,
                soft=False,
                name_ids=draft.name_ids,
                description_ids=draft.description_ids,
                flag_ids=draft.flag_ids,
                department_ids=draft.department_ids,
                field_ids=draft.field_ids,
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


async def _refresh_parameter_drafts(
    pool: asyncpg.Pool,
    redis: Redis,
    *,
    profile_id: UUID,
    session_id: UUID,
    operation_key: UUID | None,
    soft: bool = False,
) -> None:
    """Refresh parameter draft state using the canonical call shape when available.

    The refreshed parameter helper in this branch still exposes the older
    signature, so we prefer the canonical session/targets/operation key form
    and fall back to the legacy call only when needed.
    """

    try:
        await refresh_parameter_impl(
            pool,
            redis,
            profile_id=profile_id,
            session_id=session_id,
            targets=["parameter_drafts_mv"],
            soft=soft,
            operation_key=operation_key,
        )
    except TypeError as exc:
        if "unexpected keyword argument" not in str(exc):
            raise
        await refresh_parameter_impl(pool, redis, profile_id=profile_id)


async def patch_parameter_draft_impl(
    pool: asyncpg.Pool,
    redis: Redis,
    *,
    profile_id: UUID,
    session_id: UUID,
    request: PatchParameterDraftApiRequest | None = None,
    draft_id: UUID | None = None,
    soft: bool = False,
    accept: bool | None = None,
    idempotency_key: UUID | None = None,
    **kwargs: Any,
) -> PatchParameterDraftApiResponse:
    """Parameter draft using the canonical request/response contract."""

    if request is not None:
        idempotency_key = idempotency_key or request.idempotency_key
        if idempotency_key is not None and accept is None:
            accept = request.accept

    with timed("profile"):
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

    with timed("permissions"):
        if not compute_can_draft(
            role_level=profile.role_level,
            role_permissions=profile.role_permissions,
        ):
            raise HTTPException(
                status_code=403,
                detail="You don't have permission to create or edit parameter drafts.",
            )

    if accept is not None and idempotency_key is not None:
        async with pool.acquire() as conn:
            entry = await get_soft_call(conn, idempotency_key, redis, artifact=ARTIFACT)
        if entry is None or entry.status != "pending" or entry.operation != OPERATION:
            raise HTTPException(
                status_code=404,
                detail="No pending parameter draft for this call.",
            )
        target_id = entry.artifact_id

        if accept:
            async with pool.acquire() as conn:
                await enforce_draft_owner(
                    conn,
                    redis,
                    draft_id=target_id,
                    getter=get_parameter_drafts,
                    caller_session_id=session_id,
                    caller_profile_id=profile.profiles_id,
                    role_level=profile.role_level,
                    artifact=ARTIFACT,
                )
                drafts = await get_parameter_drafts(conn, [target_id], redis, active=None)
                async with transaction_with_writeback(conn):
                    if drafts:
                        draft = drafts[0]
                        await create_parameter_draft(
                            conn,
                            redis, session_id=session_id,
                            id=target_id,
                            soft=False,
                            name_ids=draft.name_ids,
                            description_ids=draft.description_ids,
                            flag_ids=draft.flag_ids,
                            department_ids=draft.department_ids,
                            field_ids=draft.field_ids,
                            profile_ids=draft.profile_ids or [profile.profiles_id],
                            pending_ids=set(),
                        )
                    else:
                        await create_parameter_draft(
                            conn,
                            redis, session_id=session_id,
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

        await _refresh_parameter_drafts(
            pool,
            redis,
            profile_id=profile_id,
            session_id=session_id,
            operation_key=idempotency_key,
        )
        return PatchParameterDraftApiResponse(
            success=True,
            draft_id=target_id,
            idempotency_key=idempotency_key,
            message="Draft accepted" if accept else "Draft rejected",
            form_state=DraftFormState(),
        )

    if request is None:
        filtered = sanitize_model_kwargs(
            kwargs,
            list_fields={
                "flag_ids",
                "department_ids",
                "field_ids",
                "departments",
                "parameter_fields",
                "pending_ids",
            },
            value_id_pairs=[
                ("name", "name_id"),
                ("description", "description_id"),
            ],
        )
        if draft_id is not None:
            filtered["draft_id"] = draft_id
            filtered["input_draft_id"] = draft_id
        request = PatchParameterDraftApiRequest(**filtered)

    if draft_id is not None and request.draft_id is None:
        request.draft_id = draft_id
    if draft_id is not None and request.input_draft_id is None:
        request.input_draft_id = draft_id
    if (
        request.draft_id is not None
        and request.input_draft_id is None
    ):
        request.input_draft_id = request.draft_id

    with timed("resolve_values"):
        async with pool.acquire() as conn:
            errors = await _resolve_creatable_values(conn, redis, request)
    if errors:
        raise HTTPException(
            status_code=400,
            detail=[error.model_dump() for error in errors],
        )

    with timed("db_write"):
     async with pool.acquire() as conn:
        await enforce_draft_owner(
            conn,
            redis,
            draft_id=idempotency_key,
            getter=get_parameter_drafts,
            caller_session_id=session_id,
            caller_profile_id=profile.profiles_id,
            role_level=profile.role_level,
            artifact=ARTIFACT,
        )
        async with transaction_with_writeback(conn):
            result = await create_parameter_draft(
                conn,
                redis, session_id=session_id,
                id=idempotency_key,
                soft=soft,
                name=request.name or "",
                name_ids=[request.name_id] if request.name_id else None,
                description_ids=[request.description_id]
                if request.description_id
                else None,
                flag_ids=request.flag_ids,
                department_ids=request.department_ids,
                field_ids=request.field_ids,
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

    auto_accepted = False
    if not soft:
        with timed("auto_accept"):
            auto_accepted = await _maybe_auto_accept_parameter_draft(
                pool, redis,
                draft_id=result.id,
                session_id=session_id,
                profile_ids=[profile.profiles_id],
            )

    form_state = DraftFormState(
        name_id=request.name_id,
        name=request.name,
        description_id=request.description_id,
        description=request.description,
        flag_ids=request.flag_ids or [],
        department_ids=request.department_ids or [],
        field_ids=request.field_ids or [],
        pending_ids=request.pending_ids or [],
    )

    if not soft:
        with timed("refresh"):
            await _refresh_parameter_drafts(
                pool,
                redis,
                profile_id=profile_id,
                session_id=session_id,
                operation_key=idempotency_key or result.id,
            )

    response_idempotency_key = idempotency_key or result.id

    if auto_accepted:
        message = "Draft accepted (all fields resolved)"
    elif soft:
        message = "Draft created (pending acceptance)"
    else:
        message = "Draft created successfully"

    return PatchParameterDraftApiResponse(
        success=True,
        draft_id=result.id,
        idempotency_key=response_idempotency_key,
        message=message,
        form_state=form_state,
    )
