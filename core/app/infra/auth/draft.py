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
from app.infra.server_timing import timed
from app.tools.entries.auth_drafts.create import create_auth_draft
from app.tools.entries.auth_drafts.get import get_auth_drafts
from app.tools.entries.soft_calls.create import create_soft_call
from app.tools.entries.soft_calls.get import get_soft_call
from app.tools.entries.soft_calls.refresh import refresh_soft_calls
from app.tools.entries.soft_calls.search import search_soft_calls
from app.tools.resources.departments.search import search_departments
from app.tools.resources.descriptions.create import create_description
from app.tools.resources.descriptions.search import search_descriptions
from app.tools.resources.flags.search import search_flags
from app.tools.resources.names.create import create_name
from app.tools.resources.names.search import search_names
from app.tools.resources.protocols.create import create_protocol
from app.tools.resources.protocols.search import search_protocols
from app.tools.resources.slugs.create import create_slug
from app.tools.resources.slugs.search import search_slugs

AUTH_ACTIVE_FLAG = "auth_active"
ARTIFACT = "auth"
OPERATION = "draft"


async def _maybe_auto_accept_auth_draft(
    pool: asyncpg.Pool,
    redis: Redis,
    *,
    draft_id: UUID,
    session_id: UUID,
    profile_ids: list[UUID],
) -> bool:
    """Auto-accept an auth draft when no pending fields remain.

    Mirrors persona/draft.py::_maybe_auto_accept_draft.
    """
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
        drafts = await get_auth_drafts(conn, [draft_id], redis, active=None)
    if not drafts:
        return False
    draft = drafts[0]
    if (
        draft.pending_department_ids
        or draft.pending_description_ids
        or draft.pending_flag_ids
        or draft.pending_item_ids
        or draft.pending_name_ids
        or draft.pending_protocol_ids
        or draft.pending_slug_ids
    ):
        return False

    async with pool.acquire() as conn:
        async with conn.transaction():
            await create_auth_draft(
                conn,
                redis, session_id=session_id,
                id=draft_id,
                soft=False,
                department_ids=draft.department_ids,
                description_ids=draft.description_ids,
                flag_ids=draft.flag_ids,
                item_ids=draft.item_ids,
                name_ids=draft.name_ids,
                profile_ids=draft.profile_ids or profile_ids,
                protocol_ids=draft.protocol_ids,
                slug_ids=draft.slug_ids,
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

    # Resolve denormalized flag booleans to canonical flag_ids via (type, value)
    # lookup in flags_resource. Explicit flag_ids are retained verbatim; the
    # derived id is merged in so both forms coexist without conflict.
    denorm_flag_values: dict[str, bool] = {}
    if request.active is not None:
        denorm_flag_values[AUTH_ACTIVE_FLAG] = bool(request.active)
    if denorm_flag_values:
        async with pool.acquire() as conn:
            all_flags = await search_flags(conn, redis, search=None, limit_count=200, auth=True)
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
                    SaveAuthFieldError(
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
                if protocol_id is None:
                    created = await create_protocol(conn, value, redis)
                    protocol_id = created.id
                resolved_ids.append(protocol_id)
            request.protocol_ids = resolved_ids

    if request.slugs is not None and request.slug_ids is None:
        async with pool.acquire() as conn:
            all_slugs = await search_slugs(conn, redis, search=None, limit_count=1000, auth=True)
            slug_map = {item.value.lower(): item.id for item in all_slugs if item.value and item.id}
            resolved_ids = []
            for value in request.slugs:
                slug_id = slug_map.get(value.lower())
                if slug_id is None:
                    created = await create_slug(conn, value, redis)
                    slug_id = created.id
                resolved_ids.append(slug_id)
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

    with timed("profile"):
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
        async with pool.acquire() as conn:
            entry = await get_soft_call(conn, idempotency_key, redis, artifact=ARTIFACT)
        if entry is None or entry.status != "pending" or entry.operation != OPERATION:
            raise HTTPException(
                status_code=404,
                detail="No pending auth draft for this call.",
            )
        target_id = entry.artifact_id

        if accept:
            async with pool.acquire() as conn:
                drafts = await get_auth_drafts(conn, [target_id], redis, active=None)
                if drafts:
                    draft = drafts[0]
                    async with conn.transaction():
                        await create_auth_draft(
                            conn,
                            redis, session_id=session_id,
                            id=target_id,
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

        await refresh_auth_impl(
            pool,
            redis,
            profile_id=profile_id,
            session_id=session_id,
            operation_key=idempotency_key,
        )

        return PatchAuthDraftApiResponse(
            success=True,
            draft_id=target_id,
            idempotency_key=idempotency_key,
            message="Draft accepted" if accept else "Draft rejected",
            form_state=DraftFormState(),
        )

    with timed("resolve_values"):
        errors = await _resolve_creatable_values(pool, redis, request)
    if errors:
        raise HTTPException(status_code=400, detail=[error.model_dump() for error in errors])

    pending_ids = set(request.pending_ids or [])
    target_draft_id = resolved_draft_id or idempotency_key

    with timed("db_write"):
     async with pool.acquire() as conn:
        async with conn.transaction():
            result = await create_auth_draft(
                conn,
                redis, session_id=session_id,
                id=target_draft_id,
                soft=soft,
                name=request.name or "",
                department_ids=request.department_ids,
                description_ids=[request.description_id] if request.description_id else None,
                flag_ids=request.flag_ids or None,
                item_ids=request.item_ids,
                name_ids=[request.name_id] if request.name_id else None,
                profile_ids=[profile.profiles_id],
                protocol_ids=request.protocol_ids,
                slug_ids=request.slug_ids,
                pending_ids=pending_ids,
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
        await _maybe_auto_accept_auth_draft(
            pool, redis,
            draft_id=result.id,
            session_id=session_id,
            profile_ids=[profile.profiles_id],
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
                auth=True,
            )
        rows_by_id = {row.id: row for row in flag_rows if getattr(row, "id", None)}
        for fid in request.flag_ids:
            row = rows_by_id.get(fid)
            if not row:
                continue
            rtype = getattr(row, "type", None) or getattr(row, "name", None)
            rval = getattr(row, "value", None)
            if rtype == AUTH_ACTIVE_FLAG:
                echoed_active = rval

    form_state = DraftFormState(
        name=request.name,
        name_id=request.name_id,
        description=request.description,
        description_id=request.description_id,
        flag_ids=request.flag_ids or [],
        active=echoed_active,
        department_ids=request.department_ids or [],
        protocol_ids=request.protocol_ids or [],
        slug_ids=request.slug_ids or [],
        item_ids=request.item_ids or [],
        pending_ids=list(pending_ids),
    )

    if not soft:
        with timed("refresh"):
            await refresh_auth_impl(
                pool,
                redis,
                profile_id=profile_id,
                session_id=session_id,
                soft=soft,
                name=request.name or "",
                operation_key=result.id,
            )

    return PatchAuthDraftApiResponse(
        success=True,
        draft_id=result.id,
        idempotency_key=result.id,
        message="Draft saved successfully" if not soft else "Draft saved (pending acceptance)",
        form_state=form_state,
    )
