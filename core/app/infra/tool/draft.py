"""Tool draft logic — canonical draft + form-state flow."""

from __future__ import annotations

from typing import Any
from uuid import UUID

import asyncpg
from fastapi import HTTPException
from redis.asyncio import Redis

from app.infra.profile_identity_context import resolve_profile_identity_context
from app.infra.tool.permissions import compute_can_draft
from app.infra.tool.refresh import refresh_tool_impl
from app.infra.tool.types import (
    DraftFormState,
    PatchToolDraftApiRequest,
    PatchToolDraftApiResponse,
    SaveToolFieldError,
)
from app.infra.tools.sanitize import sanitize_model_kwargs
from app.tools.entries.tool_drafts.create import create_tool_draft
from app.tools.entries.tool_drafts.get import get_tool_drafts
from app.tools.resources.arg_positions.create import create_arg_position
from app.tools.resources.args.create import create_arg
from app.tools.resources.args_outputs.create import create_args_output
from app.tools.resources.descriptions.create import create_description
from app.tools.resources.descriptions.get import get_descriptions
from app.tools.resources.descriptions.search import search_descriptions
from app.tools.resources.flags.search import search_flags
from app.tools.resources.names.create import create_name
from app.tools.resources.names.get import get_names
from app.tools.resources.names.search import search_names


async def _resolve_creatable_values(
    pool: asyncpg.Pool,
    redis: Redis,
    request: PatchToolDraftApiRequest,
) -> list[SaveToolFieldError]:
    """Resolve raw values to resource IDs, mutating request in place."""

    errors: list[SaveToolFieldError] = []
    request.args_output_ids = request.args_output_ids or request.args_outputs_ids

    if request.name is not None and request.name_id is None:
        async with pool.acquire() as conn:
            existing = await search_names(
                conn,
                redis,
                search=request.name,
                limit_count=10,
                tool=True,
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
                tool=True,
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
            async with pool.acquire() as conn:
                created = await create_description(conn, request.description, redis)
            request.description_id = created.id

    # Resolve denormalized flag booleans to canonical flag_ids via (type, value)
    # lookup in flags_resource. Explicit flag_ids are retained verbatim; the
    # derived id is merged in so both forms coexist without conflict.
    denorm_flag_values: dict[str, bool] = {}
    if request.active is not None:
        denorm_flag_values["tool_active"] = bool(request.active)
    if denorm_flag_values:
        async with pool.acquire() as conn:
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
                    SaveToolFieldError(
                        field=flag_type,
                        message=(
                            f"Flag row not found for type={flag_type} "
                            f"value={desired_value}"
                        ),
                    )
                )
        request.flag_ids = resolved_flag_ids

    # --- Inline arg creation ---
    if request.args and not errors:
        created_arg_ids = list(request.arg_ids or [])
        async with pool.acquire() as conn:
            for arg_input in request.args:
                result = await create_arg(
                    conn,
                    name=arg_input.name,
                    field_type=arg_input.field_type,
                    redis=redis,
                    description=arg_input.description,
                    required=arg_input.required,
                    default_value=arg_input.default_value,
                )
                created_arg_ids.append(result.id)
        request.arg_ids = created_arg_ids

    if request.args_outputs and not errors:
        created_output_ids = list(request.args_output_ids or request.args_outputs_ids or [])
        async with pool.acquire() as conn:
            for out_input in request.args_outputs:
                result = await create_args_output(
                    conn,
                    args_id=out_input.args_id,
                    name=out_input.name,
                    redis=redis,
                    template=out_input.template,
                )
                created_output_ids.append(result.id)
        request.args_output_ids = created_output_ids

    if request.arg_positions and not errors:
        created_pos_ids = list(request.arg_position_ids or [])
        async with pool.acquire() as conn:
            for pos_input in request.arg_positions:
                result = await create_arg_position(
                    conn,
                    args_id=pos_input.args_id,
                    value=pos_input.value,
                    redis=redis,
                )
                created_pos_ids.append(result.id)
        request.arg_position_ids = created_pos_ids

    # Unified per-arg drafts (Arguments step card). Each entry maps 1:1 to a
    # row; the resolver creates/links the arg, then nested outputs (each
    # scoped to the resolved args_id), then a per-(args_id, value=index)
    # position. Saved rows (id present) are re-linked unchanged — saved-row
    # immutability matches the Roles pattern.
    if request.args_drafts and not errors:
        merged_arg_ids: list[UUID] = list(request.arg_ids or [])
        merged_output_ids: list[UUID] = list(
            request.args_output_ids or request.args_outputs_ids or []
        )
        merged_pos_ids: list[UUID] = list(request.arg_position_ids or [])

        async with pool.acquire() as conn:
            for index, arg_draft in enumerate(request.args_drafts):
                # Resolve the arg row (create or re-link).
                if arg_draft.id is not None:
                    resolved_arg_id: UUID = arg_draft.id
                else:
                    new_arg = await create_arg(
                        conn,
                        name=arg_draft.name,
                        field_type=arg_draft.field_type,
                        redis=redis,
                        description=arg_draft.description,
                        required=arg_draft.required,
                        default_value=arg_draft.default_value,
                    )
                    resolved_arg_id = new_arg.id
                    arg_draft.id = resolved_arg_id
                if resolved_arg_id not in merged_arg_ids:
                    merged_arg_ids.append(resolved_arg_id)

                # Resolve nested outputs.
                for output_draft in arg_draft.outputs or []:
                    if output_draft.id is not None:
                        if output_draft.id not in merged_output_ids:
                            merged_output_ids.append(output_draft.id)
                        continue
                    new_output = await create_args_output(
                        conn,
                        args_id=resolved_arg_id,
                        name=output_draft.name,
                        redis=redis,
                        template=output_draft.template,
                    )
                    output_draft.id = new_output.id
                    if new_output.id not in merged_output_ids:
                        merged_output_ids.append(new_output.id)

                # Resolve the (args_id, value=index) position row. We always
                # create — saved rows would have come back via arg_position_ids
                # already; the unified UI never re-uses positions.
                new_position = await create_arg_position(
                    conn,
                    args_id=resolved_arg_id,
                    value=index,
                    redis=redis,
                )
                if new_position.id not in merged_pos_ids:
                    merged_pos_ids.append(new_position.id)

        request.arg_ids = merged_arg_ids
        request.args_output_ids = merged_output_ids
        request.args_outputs_ids = merged_output_ids
        request.arg_position_ids = merged_pos_ids

    return errors


async def patch_tool_draft_impl(
    pool: asyncpg.Pool,
    redis: Redis,
    *,
    profile_id: UUID,
    session_id: UUID,
    request: PatchToolDraftApiRequest | None = None,
    draft_id: UUID | None = None,
    group_id: UUID | None = None,
    soft: bool = False,
    accept: bool | None = None,
    idempotency_key: UUID | None = None,
    **kwargs: Any,
) -> PatchToolDraftApiResponse:
    """Patch tool draft using the canonical draft contract."""

    if request is None:
        filtered = sanitize_model_kwargs(
            kwargs,
            list_fields={
                "flag_ids",
                "department_ids",
                "arg_ids",
                "arg_position_ids",
                "args_output_ids",
                "args_outputs_ids",
                "permission_ids",
                "pending_ids",
            },
            bool_fields={"active"},
            value_id_pairs=[
                ("name", "name_id"),
                ("description", "description_id"),
            ],
        )
        if draft_id:
            filtered["draft_id"] = draft_id
        request = PatchToolDraftApiRequest(**filtered)

    request.draft_id = request.draft_id or request.input_draft_id or draft_id
    request.input_draft_id = request.input_draft_id or request.draft_id
    request.args_output_ids = request.args_output_ids or request.args_outputs_ids

    idempotency_key = idempotency_key or request.idempotency_key
    if idempotency_key and accept is None:
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
            detail="You don't have permission to create or edit tool drafts.",
        )

    if accept is not None and idempotency_key is not None:
        if accept:
            async with pool.acquire() as conn:
                drafts = await get_tool_drafts(conn, [idempotency_key])
                async with conn.transaction():
                    if drafts:
                        draft = drafts[0]
                        await create_tool_draft(
                            conn,
                            session_id=session_id,
                            id=idempotency_key,
                            soft=False,
                            name_ids=draft.name_ids,
                            description_ids=draft.description_ids,
                            flag_ids=draft.flag_ids,
                            department_ids=draft.department_ids,
                            arg_ids=draft.arg_ids,
                            arg_position_ids=draft.arg_position_ids,
                            args_output_ids=draft.args_output_ids,
                            instruction_ids=draft.instruction_ids,
                            permission_ids=draft.permission_ids,
                            profile_ids=draft.profile_ids or [profile.profiles_id],
                            pending_ids=set(),
                        )
                    else:
                        await create_tool_draft(
                            conn,
                            session_id=session_id,
                            id=idempotency_key,
                            soft=False,
                            profile_ids=[profile.profiles_id],
                        )
            await refresh_tool_impl(
                pool,
                redis,
                profile_id=profile_id,
                session_id=session_id,
                targets=["tool_drafts_mv"],
                operation_key=idempotency_key,
            )
        return PatchToolDraftApiResponse(
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
            result = await create_tool_draft(
                conn,
                session_id=session_id,
                id=idempotency_key,
                soft=soft,
                name=request.name or "",
                name_ids=[request.name_id] if request.name_id else None,
                description_ids=[request.description_id] if request.description_id else None,
                flag_ids=request.flag_ids or None,
                department_ids=request.department_ids,
                arg_ids=request.arg_ids,
                arg_position_ids=request.arg_position_ids,
                args_output_ids=request.args_output_ids,
                instruction_ids=[request.instruction_id]
                if request.instruction_id
                else request.instruction_ids,
                permission_ids=request.permission_ids,
                profile_ids=[profile.profiles_id],
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
            if rtype == "tool_active":
                echoed_active = rval

    form_state = DraftFormState(
        name_id=request.name_id,
        name=resolved_name,
        description_id=request.description_id,
        description=resolved_description,
        flag_ids=request.flag_ids or [],
        active=echoed_active,
        department_ids=request.department_ids or [],
        arg_ids=request.arg_ids or [],
        arg_position_ids=request.arg_position_ids or [],
        args_output_ids=request.args_output_ids or [],
        args_outputs_ids=request.args_output_ids or [],
        instruction_id=request.instruction_id,
        instruction_ids=request.instruction_ids or (
            [request.instruction_id] if request.instruction_id else []
        ),
        permission_ids=request.permission_ids or [],
        pending_ids=request.pending_ids or [],
    )

    if not soft:
        await refresh_tool_impl(
            pool,
            redis,
            profile_id=profile_id,
            session_id=session_id,
            targets=["tool_drafts_mv"],
            operation_key=result.id,
        )

    return PatchToolDraftApiResponse(
        success=True,
        draft_id=result.id,
        idempotency_key=result.id,
        message="Draft created (pending acceptance)" if soft else "Draft created successfully",
        form_state=form_state,
    )
