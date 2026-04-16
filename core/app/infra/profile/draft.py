"""Profile draft logic — canonical draft + form-state flow."""

from __future__ import annotations

from typing import Any
from uuid import UUID

import asyncpg
from fastapi import HTTPException
from redis.asyncio import Redis

from app.infra.profile.permissions import compute_can_draft
from app.infra.profile.refresh import refresh_profile_impl
from app.infra.profile.types import (
    DraftFormState,
    PatchProfileDraftApiRequest,
    PatchProfileDraftApiResponse,
    SaveProfileFieldError,
)
from app.infra.profile_identity_context import resolve_profile_identity_context
from app.infra.tools.sanitize import sanitize_model_kwargs
from app.tools.entries.profile_drafts.create import create_profile_draft
from app.tools.resources.departments.search import search_departments
from app.tools.resources.emails.create import create_email
from app.tools.resources.emails.search import search_emails
from app.tools.resources.flags.search import search_flags
from app.tools.resources.names.create import create_name
from app.tools.resources.names.search import search_names
from app.tools.resources.roles.search import search_roles


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

    if request.active_flag_id is None:
        request.active_flag_id = None

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
        if accept:
            async with pool.acquire() as conn:
                async with conn.transaction():
                    await create_profile_draft(
                        conn,
                        session_id=session_id,
                        id=idempotency_key,
                        soft=False,
                        profile_ids=[profile.profiles_id],
                        pending_ids=set(request.pending_ids) if request.pending_ids else None,
                    )
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
            result = await create_profile_draft(
                conn,
                session_id=session_id,
                id=idempotency_key,
                soft=soft,
                profile_ids=[profile.profiles_id],
                name_ids=[request.name_id] if request.name_id else None,
                flag_ids=[request.active_flag_id] if request.active_flag_id else None,
                department_ids=request.department_ids,
                email_ids=request.email_ids,
                role_ids=[request.role_id] if request.role_id else None,
                pending_ids=set(request.pending_ids) if request.pending_ids else None,
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

    form_state = DraftFormState(
        name_id=request.name_id,
        name=request.name,
        flag_id=request.active_flag_id,
        active_flag_id=request.active_flag_id,
        departments=resolved_department_names,
        department_ids=request.department_ids or [],
        emails=resolved_emails if resolved_emails else raw_emails_from_request(request),
        email_ids=request.email_ids or [],
        role=resolved_role_name,
        role_id=request.role_id,
        pending_ids=request.pending_ids or [],
    )

    if not soft:
        await refresh_profile_impl(
            pool,
            redis,
            profile_id=profile_id,
            session_id=session_id,
            targets=["profile_drafts_mv"],
            operation_key=result.id,
        )

    return PatchProfileDraftApiResponse(
        success=True,
        draft_id=result.id,
        idempotency_key=result.id,
        message="Draft created (pending acceptance)" if soft else "Draft created successfully",
        form_state=form_state,
    )


def raw_emails_from_request(request: PatchProfileDraftApiRequest) -> list[str]:
    values: list[str] = []
    if request.email:
        values.append(request.email)
    if request.emails:
        values.extend(request.emails)
    return values
