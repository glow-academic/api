"""Rubric draft logic — canonical surface over existing draft tools."""

from __future__ import annotations

from typing import Any
from uuid import UUID

import asyncpg
from fastapi import HTTPException
from redis.asyncio import Redis

from app.infra.profile_identity_context import resolve_profile_identity_context
from app.infra.rubric.permissions import compute_can_draft
from app.infra.rubric.permissions_context import resolve_rubric_point_totals
from app.infra.rubric.refresh import refresh_rubric_impl
from app.infra.rubric.types import (
    DraftFormState,
    PatchRubricDraftApiRequest,
    PatchRubricDraftApiResponse,
    SaveRubricFieldError,
)
from app.tools.entries.rubric_drafts.create import create_rubric_draft
from app.tools.entries.rubric_drafts.get import get_rubric_drafts
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
from app.tools.resources.standard_groups.create import create_standard_group
from app.tools.resources.standards.create import create_standard

ARTIFACT = "rubric"
OPERATION = "draft"


async def _maybe_auto_accept_rubric_draft(
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
        drafts = await get_rubric_drafts(conn, [draft_id], active=None)
    if not drafts:
        return False
    draft = drafts[0]
    if (
        draft.pending_department_ids
        or draft.pending_description_ids
        or draft.pending_flag_ids
        or draft.pending_name_ids
        or draft.pending_point_ids
        or draft.pending_standard_group_ids
        or draft.pending_standard_ids
    ):
        return False

    async with pool.acquire() as conn:
        async with conn.transaction():
            await create_rubric_draft(
                conn,
                session_id=session_id,
                id=draft_id,
                soft=False,
                name_ids=draft.name_ids,
                description_ids=draft.description_ids,
                flag_ids=draft.flag_ids,
                department_ids=draft.department_ids,
                point_ids=draft.point_ids,
                standard_group_ids=draft.standard_group_ids,
                standard_ids=draft.standard_ids,
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
    request: PatchRubricDraftApiRequest,
    *,
    profile_department_ids: list[UUID] | None,
) -> list[SaveRubricFieldError]:
    """Resolve raw value fields to resource IDs (mutates request in place)."""

    errors: list[SaveRubricFieldError] = []

    if request.name is not None and request.name_id is None:
        results = await search_names(
            conn,
            redis,
            search=request.name,
            limit_count=20,
            rubric=True,
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
            rubric=True,
        )
        match_id = _exact_match_id(results, request.description, attr="description")
        if match_id is None:
            match_id = (await create_description(conn, request.description, redis)).id
        request.description_id = match_id

    # Resolve denormalized flag booleans to canonical flag_ids via (type, value)
    # lookup in flags_resource. Rubric surfaces three flag types: rubric_active,
    # simulation_rubric, video_rubric. Explicit flag_ids retained verbatim.
    denorm_flag_values: dict[str, bool] = {}
    if request.active is not None:
        denorm_flag_values["rubric_active"] = bool(request.active)
    if request.simulation_rubric is not None:
        denorm_flag_values["simulation_rubric"] = bool(request.simulation_rubric)
    if request.video_rubric is not None:
        denorm_flag_values["video_rubric"] = bool(request.video_rubric)
    if denorm_flag_values:
        results = await search_flags(
            conn,
            redis,
            search=None,
            limit_count=1000,
            bypass_cache=True,
        )
        resolved_flag_ids: list[UUID] = list(request.flag_ids or [])
        resolved_seen = set(resolved_flag_ids)
        for flag_type, desired_value in denorm_flag_values.items():
            match = next(
                (
                    f
                    for f in results
                    if (
                        getattr(f, "type", None) == flag_type
                        or getattr(f, "name", None) == flag_type
                    )
                    and getattr(f, "value", None) is desired_value
                ),
                None,
            )
            if match and match.id and match.id not in resolved_seen:
                resolved_flag_ids.append(match.id)
                resolved_seen.add(match.id)
            elif not match:
                errors.append(
                    SaveRubricFieldError(
                        field=flag_type,
                        message=f"Flag row not found for type={flag_type} value={desired_value}",
                    )
                )
        request.flag_ids = resolved_flag_ids

    # Pass points — resolve numeric value to a pass-type Points resource ID.
    if request.pass_points is not None and request.pass_points_id is None:
        from app.tools.resources.points.search import search_points
        point_results = await search_points(
            conn,
            redis,
            search=None,
            limit_count=1000,
        )
        match = next(
            (
                p
                for p in point_results
                if getattr(p, "type", None) == "pass" and p.value == request.pass_points
            ),
            None,
        )
        if match and match.id:
            request.pass_points_id = match.id
        else:
            errors.append(
                SaveRubricFieldError(
                    field="pass_points",
                    message=f"Pass points resource with value {request.pass_points} not found",
                )
            )

    if request.departments:
        results = await search_departments(
            conn,
            redis,
            search=None,
            limit_count=1000,
            offset_count=0,
            department_ids=profile_department_ids or [],
            suggest_source="all",
        )
        resolved_ids: list[UUID] = []
        for raw_value in request.departments:
            item_id = _exact_match_id(results, raw_value, attr="name")
            if item_id is None:
                errors.append(
                    SaveRubricFieldError(
                        field="departments",
                        message=f'Department "{raw_value}" not found',
                    )
                )
                continue
            resolved_ids.append(item_id)
        if not any(error.field == "departments" for error in errors):
            request.department_ids = _merge_unique(request.department_ids, resolved_ids)

    # Inline-created standard groups: entries without id are created here;
    # resulting ids merge into request.standard_group_ids. The returned value
    # list retains every entry with its filled-in id so the client can map
    # temp names back to real group rows.
    if request.standard_groups:
        resolved_group_ids: list[UUID] = []
        for value in request.standard_groups:
            if value.id is None:
                created = await create_standard_group(
                    conn,
                    name=value.name,
                    short_name=value.name,
                    description=value.description or "",
                    points=value.points,
                    pass_points=value.pass_points,
                    redis=redis,
                )
                if created.id is None:
                    errors.append(
                        SaveRubricFieldError(
                            field="standard_groups",
                            message=f'Failed to create standard group "{value.name}"',
                        )
                    )
                    continue
                value.id = created.id
            resolved_group_ids.append(value.id)
        request.standard_group_ids = _merge_unique(request.standard_group_ids, resolved_group_ids)

    # Grid-editor standards: entries without id are created here; resulting
    # ids merge into request.standard_ids so the downstream draft row sees a
    # single flat list. The returned value list retains every entry with its
    # filled-in id so the client can replace stale ids in its local grid.
    if request.standards:
        resolved_standard_ids: list[UUID] = []
        for value in request.standards:
            if value.id is None:
                created = await create_standard(
                    conn,
                    name=value.name,
                    description=value.description or "",
                    points=value.points,
                    standard_group_id=value.standard_group_id,
                    redis=redis,
                )
                if created.id is None:
                    errors.append(
                        SaveRubricFieldError(
                            field="standards",
                            message=f'Failed to create standard "{value.name}"',
                        )
                    )
                    continue
                value.id = created.id
            resolved_standard_ids.append(value.id)
        request.standard_ids = _merge_unique(request.standard_ids, resolved_standard_ids)

    return errors


async def patch_rubric_draft_impl(
    pool: asyncpg.Pool,
    redis: Redis,
    *,
    profile_id: UUID,
    session_id: UUID,
    request: PatchRubricDraftApiRequest | None = None,
    draft_id: UUID | None = None,
    soft: bool = False,
    accept: bool | None = None,
    idempotency_key: UUID | None = None,
    **kwargs: object,
) -> PatchRubricDraftApiResponse:
    """Rubric draft using the canonical request/response contract."""

    if request is None:
        request = PatchRubricDraftApiRequest(**kwargs)

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
            detail="You don't have permission to create or edit rubric drafts.",
        )

    if accept is not None and idempotency_key is not None:
        async with pool.acquire() as conn:
            entry = await get_soft_call(conn, idempotency_key, redis, artifact=ARTIFACT)
        if entry is None or entry.status != "pending" or entry.operation != OPERATION:
            raise HTTPException(
                status_code=404,
                detail="No pending rubric draft for this call.",
            )
        target_id = entry.artifact_id

        if accept:
            async with pool.acquire() as conn:
                drafts = await get_rubric_drafts(conn, [target_id], active=None)
                async with conn.transaction():
                    if drafts:
                        draft = drafts[0]
                        await create_rubric_draft(
                            conn,
                            session_id=session_id,
                            id=target_id,
                            soft=False,
                            name_ids=draft.name_ids,
                            description_ids=draft.description_ids,
                            flag_ids=draft.flag_ids,
                            department_ids=draft.department_ids,
                            point_ids=draft.point_ids,
                            standard_group_ids=draft.standard_group_ids,
                            standard_ids=draft.standard_ids,
                            profile_ids=draft.profile_ids or [profile.profiles_id],
                            pending_ids=set(),
                        )
                    else:
                        await create_rubric_draft(
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

        await refresh_rubric_impl(
            pool,
            redis,
            profile_id=profile_id,
            session_id=session_id,
            targets=["rubric_drafts_mv"],
            operation_key=idempotency_key,
        )
        return PatchRubricDraftApiResponse(
            success=True,
            draft_id=target_id,
            idempotency_key=idempotency_key,
            message="Draft accepted" if accept else "Draft rejected",
            form_state=DraftFormState(),
        )

    async with pool.acquire() as conn:
        errors = await _resolve_creatable_values(
            conn,
            redis,
            request,
            profile_department_ids=profile.department_ids,
        )
    if errors:
        raise HTTPException(
            status_code=400,
            detail=[error.model_dump() for error in errors],
        )

    # Canonical: the client sends a single flat flag_ids list covering every
    # flag-type it wants active (rubric_active, simulation_rubric, video_rubric).
    combined_flag_ids = list(request.flag_ids or [])

    # Only pass points are stored on drafts; total is computed from standard groups.
    draft_point_ids = [request.pass_points_id] if request.pass_points_id else None

    async with pool.acquire() as conn:
        async with conn.transaction():
            result = await create_rubric_draft(
                conn,
                session_id=session_id,
                id=idempotency_key,
                soft=soft,
                name=request.name or "",
                profile_ids=[profile.profiles_id],
                name_ids=[request.name_id] if request.name_id else None,
                description_ids=[request.description_id] if request.description_id else None,
                flag_ids=combined_flag_ids or None,
                department_ids=request.department_ids,
                point_ids=draft_point_ids,
                standard_group_ids=request.standard_group_ids,
                standard_ids=request.standard_ids,
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

    # Denormalize point values for the form_state echo.
    # pass_points = value of the referenced pass-type resource.
    # total_points = sum of selected standard groups' max points.
    pass_points_value, total_points_value = await resolve_rubric_point_totals(
        pool,
        redis,
        pass_points_id=request.pass_points_id,
        standard_group_ids=request.standard_group_ids,
        standard_ids=request.standard_ids,
    )

    # Re-derive denormalized booleans from the final flag_ids so the client
    # echo matches whatever the server actually persisted.
    echoed_active: bool | None = request.active
    echoed_simulation_rubric: bool | None = request.simulation_rubric
    echoed_video_rubric: bool | None = request.video_rubric
    if request.flag_ids:
        async with pool.acquire() as conn:
            flag_rows = await search_flags(
                conn,
                redis,
                search=None,
                limit_count=1000,
                bypass_cache=True,
            )
        rows_by_id = {row.id: row for row in flag_rows if getattr(row, "id", None)}
        for fid in request.flag_ids:
            row = rows_by_id.get(fid)
            if not row:
                continue
            rtype = getattr(row, "type", None) or getattr(row, "name", None)
            rval = getattr(row, "value", None)
            if rtype == "rubric_active":
                echoed_active = rval
            elif rtype == "simulation_rubric":
                echoed_simulation_rubric = rval
            elif rtype == "video_rubric":
                echoed_video_rubric = rval

    form_state = DraftFormState(
        name_id=request.name_id,
        name=request.name,
        description_id=request.description_id,
        description=request.description,
        flag_ids=list(request.flag_ids or []),
        active=echoed_active,
        simulation_rubric=echoed_simulation_rubric,
        video_rubric=echoed_video_rubric,
        department_ids=request.department_ids or [],
        pass_points_id=request.pass_points_id,
        pass_points=pass_points_value,
        total_points_id=None,  # Synthetic — computed, no backing resource row.
        total_points=total_points_value,
        standard_group_ids=request.standard_group_ids or [],
        standard_groups=request.standard_groups or [],
        standard_ids=request.standard_ids or [],
        standards=request.standards or [],
        pending_ids=request.pending_ids or [],
    )

    if soft and idempotency_key is not None:
        async with pool.acquire() as conn:
            await refresh_soft_calls(conn)

    auto_accepted = False
    if not soft:
        auto_accepted = await _maybe_auto_accept_rubric_draft(
            pool, redis,
            draft_id=result.id,
            session_id=session_id,
            profile_ids=[profile.profiles_id],
        )

    if not soft:
        await refresh_rubric_impl(
            pool,
            redis,
            profile_id=profile_id,
            session_id=session_id,
            targets=["rubric_drafts_mv"],
            operation_key=result.id,
        )

    if auto_accepted:
        message = "Draft accepted (all fields resolved)"
    elif soft:
        message = "Draft created (pending acceptance)"
    else:
        message = "Draft created successfully"

    return PatchRubricDraftApiResponse(
        success=True,
        draft_id=result.id,
        idempotency_key=result.id,
        message=message,
        form_state=form_state,
    )
