"""Provider draft logic — canonical draft + form-state flow."""

from __future__ import annotations

from typing import Any
from uuid import UUID

import asyncpg
from fastapi import HTTPException
from redis.asyncio import Redis

from app.infra.profile_identity_context import resolve_profile_identity_context
from app.infra.provider.permissions import compute_can_draft
from app.infra.provider.refresh import refresh_provider_impl
from app.infra.provider.types import (
    DraftFormState,
    PatchProviderDraftApiRequest,
    PatchProviderDraftApiResponse,
    SaveProviderFieldError,
)
from app.infra.tools.sanitize import sanitize_model_kwargs
from app.tools.entries.provider_drafts.create import create_provider_draft
from app.tools.entries.provider_drafts.get import get_provider_drafts
from app.tools.resources.departments.search import search_departments
from app.tools.resources.descriptions.create import create_description
from app.tools.resources.descriptions.get import get_descriptions
from app.tools.resources.descriptions.search import search_descriptions
from app.tools.resources.endpoints.create import create_endpoint
from app.tools.resources.endpoints.get import get_endpoints
from app.tools.resources.endpoints.search import search_endpoints
from app.tools.resources.flags.search import search_flags
from app.tools.resources.keys.create import create_key
from app.tools.resources.keys.get import get_keys
from app.tools.resources.keys.search import search_keys
from app.tools.resources.names.create import create_name
from app.tools.resources.names.get import get_names
from app.tools.resources.names.search import search_names
from app.tools.resources.values.create import create_value
from app.tools.resources.values.get import get_values
from app.tools.resources.values.search import search_values


PROVIDER_ACTIVE_FLAG = "provider_active"


async def _resolve_creatable_values(
    pool: asyncpg.Pool,
    redis: Redis,
    request: PatchProviderDraftApiRequest,
) -> list[SaveProviderFieldError]:
    """Resolve raw values to resource IDs, mutating request in place."""

    errors: list[SaveProviderFieldError] = []

    request.endpoint_ids = request.endpoint_ids or (
        [request.endpoint_id] if request.endpoint_id else None
    )
    request.key_ids = request.key_ids or ([request.key_id] if request.key_id else None)

    if request.name is not None and request.name_id is None:
        async with pool.acquire() as conn:
            existing = await search_names(
                conn,
                redis,
                search=request.name,
                limit_count=10,
                provider=True,
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
            async with pool.acquire() as conn:
                created = await create_name(conn, request.name, redis)
            request.name_id = created.id

    if request.description is not None and request.description_id is None:
        async with pool.acquire() as conn:
            existing = await search_descriptions(
                conn,
                redis,
                search=request.description,
                limit_count=10,
                provider=True,
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
            async with pool.acquire() as conn:
                created = await create_description(conn, request.description, redis)
            request.description_id = created.id

    # Resolve denormalized flag booleans to canonical flag_ids via (type, value)
    # lookup in flags_resource. Explicit flag_ids are retained verbatim.
    denorm_flag_values: dict[str, bool] = {}
    if request.active is not None:
        denorm_flag_values[PROVIDER_ACTIVE_FLAG] = bool(request.active)
    if denorm_flag_values:
        async with pool.acquire() as conn:
            all_flags = await search_flags(
                conn,
                redis,
                search=None,
                limit_count=200,
                provider=True,
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
                    SaveProviderFieldError(
                        field=flag_type,
                        message=(
                            f"Flag row not found for type={flag_type} "
                            f"value={desired_value}"
                        ),
                    )
                )
        request.flag_ids = resolved_flag_ids

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
                    SaveProviderFieldError(
                        field="departments",
                        message=f'Department "{department_name}" not found',
                    )
                )
        if not any(error.field == "departments" for error in errors):
            request.department_ids = resolved_ids

    if request.value is not None and request.value_id is None:
        async with pool.acquire() as conn:
            existing = await search_values(
                conn,
                redis,
                search=request.value,
                limit_count=10,
                provider=True,
            )
        match = next(
            (
                item
                for item in existing
                if item.value and item.value.lower() == request.value.lower()
            ),
            None,
        )
        if match and match.id:
            request.value_id = match.id
        else:
            async with pool.acquire() as conn:
                created = await create_value(conn, request.value, redis, value_type="provider")
            request.value_id = created.id

    if request.endpoint is not None and not request.endpoint_ids:
        async with pool.acquire() as conn:
            existing = await search_endpoints(
                conn,
                redis,
                search=request.endpoint,
                limit_count=10,
                provider=True,
            )
        match = next(
            (
                item
                for item in existing
                if item.base_url and item.base_url.lower() == request.endpoint.lower()
            ),
            None,
        )
        if match and match.id:
            request.endpoint_ids = [match.id]
        else:
            async with pool.acquire() as conn:
                created = await create_endpoint(conn, request.endpoint, redis)
            request.endpoint_ids = [created.id]

    if request.key is not None and not request.key_ids:
        async with pool.acquire() as conn:
            created = await create_key(
                conn,
                redis,
                key=request.key,
                name=request.key_name or "Provider key",
                description=request.key_description or "",
            )
        request.key_ids = [created.id]
    elif request.key_name is not None and not request.key_ids:
        async with pool.acquire() as conn:
            existing = await search_keys(
                conn,
                redis,
                search=request.key_name,
                limit_count=20,
                provider=True,
            )
        match = next(
            (
                item
                for item in existing
                if item.name and item.name.lower() == request.key_name.lower()
            ),
            None,
        )
        if match and match.id:
            request.key_ids = [match.id]
        else:
            errors.append(
                SaveProviderFieldError(
                    field="key_name",
                    message=f'Key "{request.key_name}" not found',
                )
            )

    return errors


async def patch_provider_draft_impl(
    pool: asyncpg.Pool,
    redis: Redis,
    *,
    profile_id: UUID,
    session_id: UUID,
    request: PatchProviderDraftApiRequest | None = None,
    draft_id: UUID | None = None,
    group_id: UUID | None = None,
    soft: bool = False,
    accept: bool | None = None,
    idempotency_key: UUID | None = None,
    **kwargs: Any,
) -> PatchProviderDraftApiResponse:
    """Patch provider draft using the canonical draft contract."""

    if request is None:
        filtered = sanitize_model_kwargs(
            kwargs,
            list_fields={
                "departments",
                "department_ids",
                "endpoint_ids",
                "key_ids",
                "pending_ids",
            },
            value_id_pairs=[
                ("name", "name_id"),
                ("description", "description_id"),
                ("value", "value_id"),
                ("endpoint", "endpoint_id"),
            ],
        )
        if draft_id:
            filtered["draft_id"] = draft_id
        request = PatchProviderDraftApiRequest(**filtered)

    request.draft_id = request.draft_id or request.input_draft_id or draft_id
    request.input_draft_id = request.input_draft_id or request.draft_id
    idempotency_key = idempotency_key or request.idempotency_key
    if accept is None and idempotency_key is not None:
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
            detail="You don't have permission to create or edit provider drafts.",
        )

    if accept is not None and idempotency_key is not None:
        if accept:
            async with pool.acquire() as conn:
                drafts = await get_provider_drafts(conn, [idempotency_key])
                async with conn.transaction():
                    if drafts:
                        draft = drafts[0]
                        await create_provider_draft(
                            conn,
                            session_id=session_id,
                            id=idempotency_key,
                            soft=False,
                            name_ids=draft.name_ids,
                            description_ids=draft.description_ids,
                            flag_ids=draft.flag_ids,
                            department_ids=draft.department_ids,
                            endpoint_ids=draft.endpoint_ids,
                            key_ids=draft.key_ids,
                            value_id=draft.value_id,
                            profile_ids=draft.profile_ids or [profile.profiles_id],
                            pending_ids=set(),
                        )
                    else:
                        await create_provider_draft(
                            conn,
                            session_id=session_id,
                            id=idempotency_key,
                            soft=False,
                            profile_ids=[profile.profiles_id],
                        )
            await refresh_provider_impl(
                pool,
                redis,
                profile_id=profile_id,
                session_id=session_id,
                targets=["provider_drafts_mv"],
                operation_key=idempotency_key,
            )
        return PatchProviderDraftApiResponse(
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

    async with pool.acquire() as conn:
        async with conn.transaction():
            result = await create_provider_draft(
                conn,
                session_id=session_id,
                id=idempotency_key,
                soft=soft,
                profile_ids=[profile.profiles_id],
                name_ids=[request.name_id] if request.name_id else None,
                description_ids=[request.description_id] if request.description_id else None,
                flag_ids=request.flag_ids or None,
                department_ids=request.department_ids,
                endpoint_ids=request.endpoint_ids,
                key_ids=request.key_ids,
                value_id=request.value_id,
                pending_ids=set(request.pending_ids) if request.pending_ids else None,
            )

    resolved_name = request.name
    if request.name_id and resolved_name is None:
        matches = await get_names(pool, [request.name_id], redis, bypass_cache=True)
        resolved_name = matches[0].name if matches else None

    resolved_description = request.description
    if request.description_id and resolved_description is None:
        matches = await get_descriptions(pool,
            [request.description_id],
            redis,
            bypass_cache=True,
        )
        resolved_description = matches[0].description if matches else None

    resolved_department_names: list[str] = []
    if request.department_ids:
        async with pool.acquire() as conn:
            all_departments = await search_departments(
                conn,
                redis,
                search=None,
                limit_count=1000,
            )
        department_name_map = {
            item.id: item.name
            for item in all_departments
            if item.id and item.name
        }
        resolved_department_names = [
            department_name_map[department_id]
            for department_id in request.department_ids
            if department_id in department_name_map
        ]

    resolved_value = request.value
    if request.value_id and resolved_value is None:
        matches = await get_values(pool, [request.value_id], redis, bypass_cache=True)
        resolved_value = matches[0].value if matches else None

    resolved_endpoint = request.endpoint
    resolved_endpoint_ids = request.endpoint_ids or []
    if resolved_endpoint_ids and resolved_endpoint is None:
        matches = await get_endpoints(pool,
            resolved_endpoint_ids,
            redis,
            bypass_cache=True,
        )
        resolved_endpoint = matches[0].base_url if matches else None

    resolved_key = request.key
    resolved_key_name = request.key_name
    resolved_key_description = request.key_description
    resolved_key_ids = request.key_ids or []
    if resolved_key_ids and (
        resolved_key is None or resolved_key_name is None or resolved_key_description is None
    ):
        matches = await get_keys(pool, resolved_key_ids, redis, bypass_cache=True)
        if matches:
            resolved_key = resolved_key if resolved_key is not None else matches[0].key
            resolved_key_name = (
                resolved_key_name if resolved_key_name is not None else matches[0].name
            )
            resolved_key_description = (
                resolved_key_description
                if resolved_key_description is not None
                else matches[0].description
            )

    # Re-derive denormalized flag bool from final flag_ids so the client echo
    # matches what the server actually persisted.
    echoed_active: bool | None = request.active
    if request.flag_ids:
        async with pool.acquire() as conn:
            flag_rows = await search_flags(
                conn,
                redis,
                search=None,
                limit_count=200,
                provider=True,
            )
        rows_by_id = {row.id: row for row in flag_rows if getattr(row, "id", None)}
        for fid in request.flag_ids:
            row = rows_by_id.get(fid)
            if not row:
                continue
            rtype = getattr(row, "type", None) or getattr(row, "name", None)
            rval = getattr(row, "value", None)
            if rtype == PROVIDER_ACTIVE_FLAG:
                echoed_active = rval

    form_state = DraftFormState(
        name_id=request.name_id,
        name=resolved_name,
        description_id=request.description_id,
        description=resolved_description,
        flag_ids=request.flag_ids or [],
        active=echoed_active,
        departments=resolved_department_names,
        department_ids=request.department_ids or [],
        endpoint=resolved_endpoint,
        endpoint_id=resolved_endpoint_ids[0] if resolved_endpoint_ids else None,
        endpoint_ids=resolved_endpoint_ids,
        key=resolved_key,
        key_name=resolved_key_name,
        key_description=resolved_key_description,
        key_id=resolved_key_ids[0] if resolved_key_ids else None,
        key_ids=resolved_key_ids,
        value=resolved_value,
        value_id=request.value_id,
        pending_ids=request.pending_ids or [],
    )

    if not soft:
        await refresh_provider_impl(
            pool,
            redis,
            profile_id=profile_id,
            session_id=session_id,
            targets=["provider_drafts_mv"],
            operation_key=result.id,
        )

    return PatchProviderDraftApiResponse(
        success=True,
        draft_id=result.id,
        idempotency_key=result.id,
        message="Draft created (pending acceptance)" if soft else "Draft created successfully",
        form_state=form_state,
    )
