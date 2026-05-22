"""Eval draft logic — canonical draft-first architecture."""

from __future__ import annotations

from typing import Any
from uuid import UUID

import asyncpg
from fastapi import HTTPException
from redis.asyncio import Redis

from app.infra.eval.permissions import compute_can_draft
from app.infra.eval.refresh import refresh_eval_impl
from app.infra.eval.types import (
    DraftFormState,
    EvalModelFlagValue,
    PatchEvalDraftApiRequest,
    PatchEvalDraftApiResponse,
    SaveEvalFieldError,
)
from app.infra.profile_identity_context import resolve_profile_identity_context
from app.infra.server_timing import timed
from app.tools.entries.eval_drafts.create import create_eval_draft
from app.tools.entries.eval_drafts.get import get_eval_drafts
from app.tools.entries.soft_calls.create import create_soft_call
from app.tools.entries.soft_calls.get import get_soft_call
from app.tools.entries.soft_calls.refresh import refresh_soft_calls
from app.tools.entries.soft_calls.search import search_soft_calls
from app.tools.resources.departments.search import search_departments

ARTIFACT = "eval"
OPERATION = "draft"


async def _maybe_auto_accept_eval_draft(
    pool: asyncpg.Pool,
    redis: Redis,
    *,
    draft_id: UUID,
    session_id: UUID,
    profile_ids: list[UUID],
) -> bool:
    """Merge step — auto-accept the draft when no pending fields remain."""
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
        drafts = await get_eval_drafts(conn, [draft_id], redis, active=None)
    if not drafts:
        return False
    draft = drafts[0]
    if (
        getattr(draft, "pending_department_ids", None)
        or getattr(draft, "pending_description_ids", None)
        or getattr(draft, "pending_flag_ids", None)
        or getattr(draft, "pending_model_ids", None)
        or getattr(draft, "pending_name_ids", None)
        or getattr(draft, "pending_rubric_ids", None)
        or getattr(draft, "pending_model_flag_ids", None)
        or getattr(draft, "pending_model_position_ids", None)
        or getattr(draft, "pending_model_rubric_ids", None)
    ):
        return False

    async with pool.acquire() as conn:
        async with conn.transaction():
            await create_eval_draft(
                conn,
                redis, session_id=session_id,
                id=draft_id,
                soft=False,
                department_ids=draft.department_ids,
                description_ids=draft.description_ids,
                flag_ids=draft.flag_ids,
                model_ids=draft.model_ids,
                name_ids=draft.name_ids,
                profile_ids=draft.profile_ids or profile_ids,
                rubric_ids=draft.rubric_ids,
                model_flag_ids=draft.model_flag_ids,
                model_position_ids=draft.model_position_ids,
                model_rubric_ids=draft.model_rubric_ids,
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
from app.tools.resources.descriptions.create import create_description
from app.tools.resources.descriptions.search import search_descriptions
from app.tools.resources.flags.search import search_flags
from app.tools.resources.model_flags.create import create_model_flag
from app.tools.resources.model_flags.search import search_model_flags
from app.tools.resources.names.create import create_name
from app.tools.resources.names.search import search_names


async def _resolve_creatable_values(
    conn: asyncpg.Connection,
    redis: Redis,
    request: PatchEvalDraftApiRequest,
) -> list[SaveEvalFieldError]:
    """Resolve raw values to resource IDs, mutating the request in place."""

    errors: list[SaveEvalFieldError] = []

    if request.name is not None and request.name_id is None:
        existing = await search_names(
            conn,
            redis,
            search=request.name,
            limit_count=1,
            eval=True,
        )
        match = next(
            (item for item in existing if item.name and item.name.lower() == request.name.lower()),
            None,
        )
        if match and match.id:
            request.name_id = match.id
        else:
            result = await create_name(conn, request.name, redis)
            request.name_id = result.id

    if request.description is not None and request.description_id is None:
        existing = await search_descriptions(
            conn,
            redis,
            search=request.description,
            limit_count=1,
            eval=True,
        )
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

    # Resolve denormalized flag booleans (active) to canonical flag_ids via
    # (type, value) lookup in flags_resource. Explicit flag_ids are retained.
    denorm_flag_values: dict[str, bool] = {}
    if request.active is not None:
        denorm_flag_values["eval_active"] = bool(request.active)
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
                    SaveEvalFieldError(
                        field=flag_type,
                        message=f"Flag row not found for type={flag_type} value={desired_value}",
                    )
                )
        request.flag_ids = resolved_flag_ids

    # Denormalized model-flag entries -> junction-row IDs.
    # Two input shapes resolve here:
    #   * request.model_flags: [{model_id, flag_id}] inline-create pairs
    #   * request.model_flag_values: [{model_id, type, value}] denormalized
    # For each, find/create the matching model_flags_resource row and merge
    # its id into request.model_flag_ids (dedup).
    if request.model_flags or request.model_flag_values:
        existing_ids: list[UUID] = list(request.model_flag_ids or [])
        seen_junction_ids: set[UUID] = set(existing_ids)

        # Inline (model_id, flag_id) pairs: upsert junction row.
        for entry in request.model_flags or []:
            model_id = entry.get("model_id") if isinstance(entry, dict) else None
            flag_id = entry.get("flag_id") if isinstance(entry, dict) else None
            if not model_id or not flag_id:
                continue
            existing = await search_model_flags(
                conn,
                redis,
                limit_count=1,
                model_ids=[UUID(str(model_id))],
                flag_ids=[UUID(str(flag_id))],
                bypass_cache=True,
                eval=True,
            )
            if existing:
                jid = existing[0].id
            else:
                created = await create_model_flag(
                    conn,
                    UUID(str(model_id)),
                    UUID(str(flag_id)),
                    redis,
                )
                jid = created.id
            if jid and jid not in seen_junction_ids:
                existing_ids.append(jid)
                seen_junction_ids.add(jid)

        # Denormalized (model_id, type, value) entries: resolve (type, value)
        # -> flag_id first, then upsert the junction.
        if request.model_flag_values:
            all_flags = await search_flags(
                conn,
                redis,
                search=None,
                limit_count=200,
                bypass_cache=True,
            )
            for entry in request.model_flag_values:
                desired_type = entry.type
                desired_value = bool(entry.value)
                match = next(
                    (
                        f
                        for f in all_flags
                        if (
                            getattr(f, "type", None) == desired_type
                            or getattr(f, "name", None) == desired_type
                        )
                        and getattr(f, "value", None) is desired_value
                    ),
                    None,
                )
                if not match or not match.id:
                    errors.append(
                        SaveEvalFieldError(
                            field="model_flag_values",
                            message=(
                                f"Flag row not found for type={desired_type} "
                                f"value={desired_value}"
                            ),
                        )
                    )
                    continue
                existing = await search_model_flags(
                    conn,
                    redis,
                    limit_count=1,
                    model_ids=[entry.model_id],
                    flag_ids=[match.id],
                    bypass_cache=True,
                    eval=True,
                )
                if existing:
                    jid = existing[0].id
                else:
                    created = await create_model_flag(
                        conn,
                        entry.model_id,
                        match.id,
                        redis,
                    )
                    jid = created.id
                if jid and jid not in seen_junction_ids:
                    existing_ids.append(jid)
                    seen_junction_ids.add(jid)

        request.model_flag_ids = existing_ids

    if request.departments is not None and request.department_ids is None:
        all_departments = await search_departments(
            conn,
            redis,
            search=None,
            limit_count=1000,
        )
        department_name_map = {
            item.name.lower(): item.department_id
            for item in all_departments
            if item.name and item.department_id
        }
        resolved_ids: list[UUID] = []
        for department_name in request.departments:
            department_id = department_name_map.get(department_name.lower())
            if department_id:
                resolved_ids.append(department_id)
            else:
                errors.append(
                    SaveEvalFieldError(
                        field="departments",
                        message=f'Department "{department_name}" not found',
                    )
                )
        if not any(error.field == "departments" for error in errors):
            request.department_ids = resolved_ids

    return errors


async def patch_eval_draft_impl(
    pool: asyncpg.Pool,
    redis: Redis,
    *,
    profile_id: UUID,
    session_id: UUID,
    request: PatchEvalDraftApiRequest | None = None,
    draft_id: UUID | None = None,
    soft: bool = False,
    accept: bool | None = None,
    idempotency_key: UUID | None = None,
    **kwargs: Any,
) -> PatchEvalDraftApiResponse:
    """Eval draft using the canonical request/response contract."""

    if request is None:
        request = PatchEvalDraftApiRequest(**kwargs)

    request.draft_id = request.draft_id or request.input_draft_id or draft_id
    request.input_draft_id = request.input_draft_id or request.draft_id

    resolved_draft_id = request.draft_id or request.input_draft_id
    # Idempotency key must be EXPLICIT — either passed by the generation
    # pipeline as a kwarg or sent on the request. Falling back to the
    # request's draft_id here caused subsequent autosaves (which always
    # include the existing draft_id but never set idempotency_key) to be
    # misrouted into the `accept` branch below, which copies the OLD
    # draft's junction IDs forward and drops the client's new model_ids.
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
                detail="You don't have permission to create or edit eval drafts.",
            )

    if accept is not None and idempotency_key is not None:
        async with pool.acquire() as conn:
            entry = await get_soft_call(conn, idempotency_key, redis, artifact=ARTIFACT)
        if entry is None or entry.status != "pending" or entry.operation != OPERATION:
            raise HTTPException(
                status_code=404,
                detail="No pending eval draft for this call.",
            )
        target_id = entry.artifact_id

        if accept:
            async with pool.acquire() as conn:
                drafts = await get_eval_drafts(conn, [target_id], redis, active=None)
                if drafts:
                    draft = drafts[0]
                    async with conn.transaction():
                        await create_eval_draft(
                            conn,
                            redis, session_id=session_id,
                            id=target_id,
                            soft=False,
                            department_ids=draft.department_ids,
                            description_ids=draft.description_ids,
                            flag_ids=draft.flag_ids,
                            model_ids=draft.model_ids,
                            name_ids=draft.name_ids,
                            profile_ids=draft.profile_ids or [profile.profiles_id],
                            rubric_ids=draft.rubric_ids,
                            model_flag_ids=draft.model_flag_ids,
                            model_position_ids=draft.model_position_ids,
                            model_rubric_ids=draft.model_rubric_ids,
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

        await refresh_eval_impl(
            pool,
            redis,
            profile_id=profile_id,
            session_id=session_id,
            operation_key=idempotency_key,
        )

        return PatchEvalDraftApiResponse(
            success=True,
            draft_id=target_id,
            idempotency_key=idempotency_key,
            message="Draft accepted" if accept else "Draft rejected",
            form_state=DraftFormState(),
        )

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
        async with conn.transaction():
            result = await create_eval_draft(
                conn,
                redis, session_id=session_id,
                id=resolved_draft_id or idempotency_key,
                soft=soft,
                name=request.name or "",
                name_ids=[request.name_id] if request.name_id else None,
                description_ids=[request.description_id] if request.description_id else None,
                flag_ids=request.flag_ids,
                department_ids=request.department_ids,
                model_ids=request.model_ids,
                model_flag_ids=request.model_flag_ids,
                model_position_ids=request.model_position_ids,
                model_rubric_ids=request.model_rubric_ids,
                profile_ids=[profile.profiles_id],
                pending_ids=set(request.pending_ids) if request.pending_ids else None,
            )

            # Pending ledger row tied to this tool call.
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

    # Re-derive denormalized active bool from the final flag_ids so the client
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
            if rtype == "eval_active":
                echoed_active = rval

    # Re-derive denormalized (model_id, type, value) echo from the final
    # model_flag_ids so the client can reconcile its per-(model, type) Switch
    # state with what the server actually persisted.
    model_flag_values_echo: list[EvalModelFlagValue] = []
    if request.model_flag_ids:
        async with pool.acquire() as conn:
            from app.tools.resources.model_flags.get import get_model_flags

            junction_rows = await get_model_flags(
                conn, list(request.model_flag_ids), redis, bypass_cache=True
            )
        flag_ids_needed = [
            r.flag_id for r in junction_rows if getattr(r, "flag_id", None)
        ]
        if flag_ids_needed:
            async with pool.acquire() as conn:
                from app.tools.resources.flags.get import get_flags

                flag_rows = await get_flags(
                    conn, flag_ids_needed, redis, bypass_cache=True
                )
            flags_by_id = {row.id: row for row in flag_rows if getattr(row, "id", None)}
            for jr in junction_rows:
                fr = flags_by_id.get(getattr(jr, "flag_id", None))
                if not fr:
                    continue
                rtype = getattr(fr, "type", None) or getattr(fr, "name", None)
                rvalue = getattr(fr, "value", None)
                if jr.model_id is None or rtype is None or rvalue is None:
                    continue
                model_flag_values_echo.append(
                    EvalModelFlagValue(
                        model_id=jr.model_id, type=rtype, value=bool(rvalue)
                    )
                )

    form_state = DraftFormState(
        name_id=request.name_id,
        name=request.name,
        description_id=request.description_id,
        description=request.description,
        flag_ids=request.flag_ids or [],
        active=echoed_active,
        department_ids=request.department_ids or [],
        model_ids=request.model_ids or [],
        model_flag_ids=request.model_flag_ids or [],
        model_flag_values=model_flag_values_echo,
        model_position_ids=request.model_position_ids or [],
        model_rubric_ids=request.model_rubric_ids or [],
        pending_ids=request.pending_ids or [],
    )

    auto_accepted = False
    if not soft:
        with timed("auto_accept"):
            auto_accepted = await _maybe_auto_accept_eval_draft(
                pool, redis,
                draft_id=result.id,
                session_id=session_id,
                profile_ids=[profile.profiles_id],
            )
        with timed("refresh"):
            await refresh_eval_impl(
                pool,
                redis,
                profile_id=profile_id,
                session_id=session_id,
                soft=soft,
                name=request.name or "",
                operation_key=result.id,
            )

    if auto_accepted:
        message = "Draft accepted (all fields resolved)"
    elif soft:
        message = "Draft created (pending acceptance)"
    else:
        message = "Draft created successfully"

    return PatchEvalDraftApiResponse(
        success=True,
        draft_id=result.id,
        idempotency_key=result.id,
        message=message,
        form_state=form_state,
    )
