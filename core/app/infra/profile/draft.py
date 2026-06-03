"""Profile draft logic — canonical draft + form-state flow."""

from __future__ import annotations

from typing import Any
from uuid import UUID

import asyncpg
from fastapi import HTTPException
from redis.asyncio import Redis

from app.infra.profile.permissions import compute_can_draft
from app.infra.profile.primary_department import (
    resolve_primary_departments_id,
)
from app.infra.profile.refresh import refresh_profile_impl
from app.infra.profile.types import (
    DraftFormState,
    PatchProfileDraftApiRequest,
    PatchProfileDraftApiResponse,
    SaveProfileFieldError,
)
from app.infra.profile_identity_context import resolve_profile_identity_context
from app.infra.server_timing import timed
from app.infra.tools.sanitize import sanitize_model_kwargs
from app.tools.entries.profile_drafts.create import create_profile_draft
from app.tools.entries.profile_drafts.get import get_profile_drafts
from app.tools.entries.soft_calls.create import create_soft_call
from app.tools.entries.soft_calls.get import get_soft_call
from app.tools.entries.soft_calls.refresh import refresh_soft_calls
from app.tools.entries.soft_calls.search import search_soft_calls

ARTIFACT = "profile"
OPERATION = "draft"
from app.tools.resources.departments.search import search_departments
from app.tools.resources.emails.create import create_email
from app.tools.resources.emails.search import search_emails
from app.tools.resources.flags.search import search_flags
from app.tools.resources.names.create import create_name
from app.tools.resources.names.search import search_names
from app.tools.resources.request_limits.create import create_request_limit
from app.tools.resources.roles.create import create_role
from app.tools.resources.roles.search import search_roles


async def _maybe_auto_accept_profile_draft(
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
        drafts = await get_profile_drafts(conn, [draft_id], redis, active=None)
    if not drafts:
        return False
    draft = drafts[0]
    if (
        draft.pending_department_ids
        or draft.pending_email_ids
        or draft.pending_flag_ids
        or draft.pending_name_ids
        or draft.pending_role_ids
        or draft.pending_primary_department_ids
    ):
        return False

    async with pool.acquire() as conn:
        async with conn.transaction():
            await create_profile_draft(
                conn,
                redis, session_id=session_id,
                id=draft_id,
                soft=False,
                name_ids=draft.name_ids,
                flag_ids=draft.flag_ids,
                department_ids=draft.department_ids,
                email_ids=draft.email_ids,
                role_ids=draft.role_ids,
                primary_department_ids=draft.primary_department_ids,
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


def _merge_unique(existing: list[UUID] | None, additions: list[UUID]) -> list[UUID]:
    merged = list(existing or [])
    for item in additions:
        if item not in merged:
            merged.append(item)
    return merged


async def _resolve_creatable_values(
    pool: asyncpg.Pool,
    redis: Redis,
    request: PatchProfileDraftApiRequest,
) -> list[SaveProfileFieldError]:
    """Resolve raw values to resource IDs, mutating request in place."""

    errors: list[SaveProfileFieldError] = []

    if request.name is not None and request.name_id is None:
        async with pool.acquire() as conn:
            existing = await search_names(
                conn,
                redis,
                search=request.name,
                limit_count=10,
                profile=True,
            )
        match = next(
            (item for item in existing if item.name and item.name.lower() == request.name.lower()),
            None,
        )
        if match and match.id:
            request.name_id = match.id
        else:
            async with pool.acquire() as conn:
                created = await create_name(conn, request.name, redis)
            request.name_id = created.id

    raw_emails = []
    if request.email:
        raw_emails.append(request.email)
    if request.emails:
        raw_emails.extend(request.emails)
    if raw_emails:
        resolved_email_ids: list[UUID] = []
        for raw_email in raw_emails:
            async with pool.acquire() as conn:
                existing = await search_emails(
                    conn,
                    redis,
                    search=raw_email,
                    limit_count=10,
                    profile=True,
                )
            match = next(
                (item for item in existing if item.email and item.email.lower() == raw_email.lower()),
                None,
            )
            if match and match.id:
                resolved_email_ids.append(match.id)
            else:
                async with pool.acquire() as conn:
                    created = await create_email(conn, raw_email, redis)
                resolved_email_ids.append(created.id)
        request.email_ids = _merge_unique(request.email_ids, resolved_email_ids)

    if request.departments is not None and request.department_ids is None:
        async with pool.acquire() as conn:
            all_departments = await search_departments(
                conn,
                redis,
                search=None,
                limit_count=1000,
            )
        dept_name_map = {
            item.name.lower(): item.id
            for item in all_departments
            if item.name and item.id
        }
        resolved_department_ids: list[UUID] = []
        for department_name in request.departments:
            department_id = dept_name_map.get(department_name.lower())
            if department_id:
                resolved_department_ids.append(department_id)
            else:
                errors.append(
                    SaveProfileFieldError(
                        field="departments",
                        message=f'Department "{department_name}" not found',
                    )
                )
        if not any(error.field == "departments" for error in errors):
            request.department_ids = resolved_department_ids

    if request.role is not None and request.role_id is None:
        async with pool.acquire() as conn:
            all_roles = await search_roles(
                conn,
                redis,
                search=request.role,
                limit_count=20,
                profile=True,
            )
        match = next(
            (item for item in all_roles if item.name and item.name.lower() == request.role.lower()),
            None,
        )
        if match and match.id:
            request.role_id = match.id
        else:
            errors.append(
                SaveProfileFieldError(
                    field="role",
                    message=f'Role "{request.role}" not found',
                )
            )

    # Inline-creatable role: create nested request_limits first, then create
    # the role with the merged permission_ids + request_limit_ids. Roles are
    # immutable on this surface, so when role_draft.id is set we just thread
    # the existing role_id through.
    role_draft = getattr(request, "role_draft", None)
    if role_draft is not None:
        if role_draft.id is not None:
            request.role_id = role_draft.id
        else:
            if not role_draft.name:
                errors.append(
                    SaveProfileFieldError(
                        field="role_draft.name",
                        message="Role name is required when creating a new role",
                    )
                )
            else:
                resolved_limit_ids: list[UUID] = list(role_draft.request_limit_ids or [])
                resolved_seen = set(resolved_limit_ids)
                async with pool.acquire() as conn:
                    for limit_value in role_draft.request_limits or []:
                        if limit_value.id is not None:
                            if limit_value.id not in resolved_seen:
                                resolved_limit_ids.append(limit_value.id)
                                resolved_seen.add(limit_value.id)
                            continue
                        created_limit = await create_request_limit(
                            conn,
                            limit=limit_value.limit,
                            redis=redis,
                            interval=limit_value.interval,
                        )
                        limit_value.id = created_limit.id
                        if created_limit.id not in resolved_seen:
                            resolved_limit_ids.append(created_limit.id)
                            resolved_seen.add(created_limit.id)

                async with pool.acquire() as conn:
                    new_role = await create_role(
                        conn,
                        redis,
                        name=role_draft.name,
                        description=role_draft.description or "",
                        icon_id=role_draft.icon_id,
                        color_id=role_draft.color_id,
                        level=role_draft.level,
                        permission_ids=list(role_draft.permission_ids or []),
                        request_limit_ids=resolved_limit_ids,
                    )
                role_draft.id = new_role.id
                role_draft.request_limit_ids = resolved_limit_ids
                request.role_id = new_role.id

    # Resolve denormalized flag booleans to canonical flag_ids.
    denorm_flag_values: dict[str, bool] = {}
    if request.active is not None:
        denorm_flag_values["profile_active"] = bool(request.active)
    if denorm_flag_values:
        async with pool.acquire() as conn:
            all_flags = await search_flags(conn, redis, search=None, limit_count=200, profile=True)
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
                    SaveProfileFieldError(
                        field=flag_type,
                        message=(
                            f"Flag row not found for type={flag_type} "
                            f"value={desired_value}"
                        ),
                    )
                )
        request.flag_ids = resolved_flag_ids

    return errors


async def patch_profile_draft_impl(
    pool: asyncpg.Pool,
    redis: Redis,
    *,
    profile_id: UUID,
    session_id: UUID,
    request: PatchProfileDraftApiRequest | None = None,
    draft_id: UUID | None = None,
    group_id: UUID | None = None,
    soft: bool = False,
    accept: bool | None = None,
    idempotency_key: UUID | None = None,
    **kwargs: Any,
) -> PatchProfileDraftApiResponse:
    """Patch profile draft using the canonical draft pattern."""

    if request is None:
        filtered = sanitize_model_kwargs(
            kwargs,
            list_fields={"emails", "departments", "department_ids", "email_ids", "pending_ids"},
            value_id_pairs=[("name", "name_id"), ("role", "role_id")],
        )
        if draft_id:
            filtered["draft_id"] = draft_id
        request = PatchProfileDraftApiRequest(**filtered)

    request.draft_id = request.draft_id or request.input_draft_id or draft_id
    request.input_draft_id = request.input_draft_id or request.draft_id

    idempotency_key = idempotency_key or request.idempotency_key
    if accept is None and idempotency_key is not None:
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

    if not compute_can_draft(
        role_level=profile.role_level,
        role_permissions=profile.role_permissions,
    ):
        raise HTTPException(
            status_code=403,
            detail="You don't have permission to create or edit profile drafts.",
        )

    if accept is not None and idempotency_key is not None:
        async with pool.acquire() as conn:
            entry = await get_soft_call(conn, idempotency_key, redis, artifact=ARTIFACT)
        if entry is None or entry.status != "pending" or entry.operation != OPERATION:
            raise HTTPException(
                status_code=404,
                detail="No pending profile draft for this call.",
            )
        target_id = entry.artifact_id

        if accept:
            async with pool.acquire() as conn:
                drafts = await get_profile_drafts(conn, [target_id], redis, active=None)
                async with conn.transaction():
                    if drafts:
                        draft = drafts[0]
                        await create_profile_draft(
                            conn,
                            redis, session_id=session_id,
                            id=target_id,
                            soft=False,
                            name_ids=draft.name_ids,
                            flag_ids=draft.flag_ids,
                            department_ids=draft.department_ids,
                            email_ids=draft.email_ids,
                            role_ids=draft.role_ids,
                            primary_department_ids=draft.primary_department_ids,
                            profile_ids=draft.profile_ids or [profile.profiles_id],
                            pending_ids=set(),
                        )
                    else:
                        await create_profile_draft(
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

        await refresh_profile_impl(
            pool,
            redis,
            profile_id=profile_id,
            session_id=session_id,
            targets=["profile_drafts_mv"],
            operation_key=idempotency_key,
        )
        return PatchProfileDraftApiResponse(
            success=True,
            draft_id=target_id,
            idempotency_key=idempotency_key,
            message="Draft accepted" if accept else "Draft rejected",
            form_state=DraftFormState(),
        )

    with timed("resolve_values"):
        errors = await _resolve_creatable_values(pool, redis, request)
    if errors:
        raise HTTPException(
            status_code=400,
            detail=[error.model_dump() for error in errors],
        )

    with timed("db_write"):
      async with pool.acquire() as conn:
        async with conn.transaction():
            primary_departments_resource_id: UUID | None = None
            if request.primary_department_id is not None:
                primary_departments_resource_id = await resolve_primary_departments_id(
                    conn,
                    redis,
                    departments_id=request.primary_department_id,
                    soft=soft,
                )

            result = await create_profile_draft(
                conn,
                redis, session_id=session_id,
                id=idempotency_key,
                soft=soft,
                name=request.name or "",
                profile_ids=[profile.profiles_id],
                name_ids=[request.name_id] if request.name_id else None,
                flag_ids=request.flag_ids or None,
                department_ids=request.department_ids,
                email_ids=request.email_ids,
                role_ids=[request.role_id] if request.role_id else None,
                primary_department_ids=(
                    [primary_departments_resource_id]
                    if primary_departments_resource_id
                    else None
                ),
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

    resolved_emails: list[str] = []
    if request.email_ids:
        async with pool.acquire() as conn:
            email_matches = await search_emails(
                conn,
                redis,
                search=None,
                limit_count=1000,
                profile=True,
            )
        email_map = {item.id: item.email for item in email_matches if item.id and item.email}
        resolved_emails = [email_map[email_id] for email_id in request.email_ids if email_id in email_map]

    resolved_department_names: list[str] = []
    if request.department_ids:
        async with pool.acquire() as conn:
            department_matches = await search_departments(
                conn,
                redis,
                search=None,
                limit_count=1000,
            )
        department_map = {item.id: item.name for item in department_matches if item.id and item.name}
        resolved_department_names = [
            department_map[department_id]
            for department_id in request.department_ids
            if department_id in department_map
        ]

    resolved_role_name = request.role
    if request.role_id and resolved_role_name is None:
        async with pool.acquire() as conn:
            role_matches = await search_roles(
                conn,
                redis,
                search=None,
                limit_count=1000,
                profile=True,
            )
        role_map = {item.id: item.name for item in role_matches if item.id and item.name}
        resolved_role_name = role_map.get(request.role_id)

    # Re-derive denormalized flag bool from final flag_ids.
    echoed_active: bool | None = request.active
    if request.flag_ids:
        async with pool.acquire() as conn:
            flag_rows = await search_flags(conn, redis, search=None, limit_count=200, profile=True)
        rows_by_id = {row.id: row for row in flag_rows if getattr(row, "id", None)}
        for fid in request.flag_ids:
            row = rows_by_id.get(fid)
            if not row:
                continue
            rtype = getattr(row, "type", None) or getattr(row, "name", None)
            rval = getattr(row, "value", None)
            if rtype == "profile_active":
                echoed_active = rval

    form_state = DraftFormState(
        name_id=request.name_id,
        name=request.name,
        flag_ids=request.flag_ids or [],
        active=echoed_active,
        departments=resolved_department_names,
        department_ids=request.department_ids or [],
        emails=resolved_emails if resolved_emails else raw_emails_from_request(request),
        email_ids=request.email_ids or [],
        role=resolved_role_name,
        role_id=request.role_id,
        primary_department_id=request.primary_department_id,
        pending_ids=request.pending_ids or [],
    )

    if soft and idempotency_key is not None:
        async with pool.acquire() as conn:
            await refresh_soft_calls(conn)

    auto_accepted = False
    if not soft:
        auto_accepted = await _maybe_auto_accept_profile_draft(
            pool, redis,
            draft_id=result.id,
            session_id=session_id,
            profile_ids=[profile.profiles_id],
        )

    if not soft:
        with timed("refresh"):
            await refresh_profile_impl(
                pool,
                redis,
                profile_id=profile_id,
                session_id=session_id,
                targets=["profile_drafts_mv"],
                operation_key=result.id,
            )

    if auto_accepted:
        message = "Draft accepted (all fields resolved)"
    elif soft:
        message = "Draft created (pending acceptance)"
    else:
        message = "Draft created successfully"

    return PatchProfileDraftApiResponse(
        success=True,
        draft_id=result.id,
        idempotency_key=result.id,
        message=message,
        form_state=form_state,
    )


def raw_emails_from_request(request: PatchProfileDraftApiRequest) -> list[str]:
    values: list[str] = []
    if request.email:
        values.append(request.email)
    if request.emails:
        values.extend(request.emails)
    return values
