"""Persona draft logic — composable infra architecture.

Core draft function that composes existing black-box tools:
  1. resolve_profile_identity_context — profile (role, departments)
  2. compute_can_draft — permission check
  3. Value resolution (creatable resources only) — raw value → ID
  4. create_persona_draft — entry tool (append-only snapshot)
  5. refresh_persona_drafts — MV refresh
  6. invalidate_tags — cache invalidation
"""

from __future__ import annotations

from typing import Any
from uuid import UUID

import asyncpg
from fastapi import HTTPException
from redis.asyncio import Redis

from app.infra.persona.permissions import compute_can_draft
from app.infra.profile_identity_context import resolve_profile_identity_context
from app.infra.persona.types import (
    DraftFormState,
    PatchPersonaDraftApiRequest,
    PatchPersonaDraftApiResponse,
    SavePersonaFieldError,
)
from app.tools.entries.persona_drafts.create import create_persona_draft
from app.tools.entries.persona_drafts.get import get_persona_drafts
from app.infra.persona.refresh import refresh_persona_impl
from app.tools.resources.colors.search import search_colors
from app.tools.resources.departments.search import search_departments
from app.tools.resources.descriptions.create import create_description
from app.tools.resources.examples.create import create_example
from app.tools.resources.fields.get import get_fields
from app.tools.resources.flags.search import search_flags
from app.tools.resources.icons.search import search_icons
from app.tools.resources.instructions.create import create_instruction
from app.tools.resources.names.create import create_name
from app.tools.resources.parameter_fields.search import search_parameter_fields
from app.tools.resources.voices.search import search_voices

# ---------------------------------------------------------------------------
# Value resolution — creatable resources only
# ---------------------------------------------------------------------------


async def _resolve_creatable_values(
    pool: asyncpg.Pool,
    redis: Redis,
    request: PatchPersonaDraftApiRequest,
) -> list[SavePersonaFieldError]:
    """Resolve raw value fields to resource IDs (mutates request in place).

    Handles creatable resources (name, description, instructions, examples)
    and match resources (color, icon, active_flag, departments, parameter_fields, voices).
    Returns a list of errors (empty if all resolved).
    """
    errors: list[SavePersonaFieldError] = []

    # --- Create resources ---

    async with pool.acquire() as conn:
        if request.name is not None and request.name_id is None:
            result = await create_name(conn, request.name, redis)
            request.name_id = result.id

        if request.description is not None and request.description_id is None:
            result = await create_description(conn, request.description, redis)
            request.description_id = result.id

        if request.instructions is not None and request.instructions_id is None:
            result = await create_instruction(conn, request.instructions, redis)
            request.instructions_id = result.id

        if request.examples is not None and request.example_ids is None:
            resolved_ids = []
            for ex in request.examples:
                result = await create_example(conn, ex, redis)
                resolved_ids.append(result.id)
            request.example_ids = resolved_ids

    # --- Match resources ---

    if request.color is not None and request.color_id is None:
        async with pool.acquire() as conn:
            results = await search_colors(
                conn, redis, search=request.color, limit_count=20
            )
        match = next(
            (r for r in results if r.name and r.name.lower() == request.color.lower()),
            None,
        )
        if match and match.id:
            request.color_id = match.id
        else:
            errors.append(
                SavePersonaFieldError(
                    field="color", message=f'Color "{request.color}" not found'
                )
            )

    if request.icon is not None and request.icon_id is None:
        async with pool.acquire() as conn:
            results = await search_icons(
                conn, redis, search=request.icon, limit_count=20
            )
        match = next(
            (r for r in results if r.name and r.name.lower() == request.icon.lower()),
            None,
        )
        if match and match.id:
            request.icon_id = match.id
        else:
            errors.append(
                SavePersonaFieldError(
                    field="icon", message=f'Icon "{request.icon}" not found'
                )
            )

    # Resolve denormalized flag booleans (active) to canonical flag_ids via
    # (type, value) lookup in flags_resource. Explicit flag_ids retained.
    denorm_flag_values: dict[str, bool] = {}
    if request.active is not None:
        denorm_flag_values["persona_active"] = bool(request.active)
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
                    SavePersonaFieldError(
                        field=flag_type,
                        message=f"Flag row not found for type={flag_type} value={desired_value}",
                    )
                )
        request.flag_ids = resolved_flag_ids

    if request.departments is not None and request.department_ids is None:
        async with pool.acquire() as conn:
            all_depts = await search_departments(
                conn, redis, search=None, limit_count=1000
            )
        dept_name_map = {d.name.lower(): d.id for d in all_depts if d.name and d.id}
        resolved_ids = []
        for dept_name in request.departments:
            dept_id = dept_name_map.get(dept_name.lower())
            if dept_id:
                resolved_ids.append(dept_id)
            else:
                errors.append(
                    SavePersonaFieldError(
                        field="departments",
                        message=f'Department "{dept_name}" not found',
                    )
                )
        if not any(e.field == "departments" for e in errors):
            request.department_ids = resolved_ids

    if request.parameter_fields is not None and request.parameter_field_ids is None:
        async with pool.acquire() as conn:
            all_pf = await search_parameter_fields(conn, redis)
        field_ids_list = [pf.field_id for pf in all_pf if pf.field_id]
        if field_ids_list:
            async with pool.acquire() as conn:
                fields_list = await get_fields(conn, field_ids_list, redis)
        else:
            fields_list = []
        field_name_map = {f.id: f.name for f in fields_list if f.name}
        pf_name_map = {
            field_name_map[pf.field_id].lower(): pf.id
            for pf in all_pf
            if pf.field_id and pf.id and pf.field_id in field_name_map
        }
        resolved_ids = []
        for pf_name in request.parameter_fields:
            pf_id = pf_name_map.get(pf_name.lower())
            if pf_id:
                resolved_ids.append(pf_id)
            else:
                errors.append(
                    SavePersonaFieldError(
                        field="parameter_fields",
                        message=f'Parameter field "{pf_name}" not found',
                    )
                )
        if not any(e.field == "parameter_fields" for e in errors):
            request.parameter_field_ids = resolved_ids

    if request.voices is not None and request.voice_ids is None:
        async with pool.acquire() as conn:
            all_voices = await search_voices(
                conn,
                redis,
                search=None,
                limit_count=1000,
            )
        voice_name_map = {v.voice.lower(): v.id for v in all_voices if v.voice and v.id}
        resolved_ids = []
        for voice_name in request.voices:
            vid = voice_name_map.get(voice_name.lower())
            if vid:
                resolved_ids.append(vid)
            else:
                errors.append(
                    SavePersonaFieldError(
                        field="voices",
                        message=f'Voice "{voice_name}" not found',
                    )
                )
        if not any(e.field == "voices" for e in errors):
            request.voice_ids = resolved_ids

    return errors


# ---------------------------------------------------------------------------
# patch_persona_draft_impl — composable infra architecture
# ---------------------------------------------------------------------------


async def patch_persona_draft_impl(
    pool: asyncpg.Pool,
    redis: Redis,
    *,
    profile_id: UUID,
    session_id: UUID,
    request: PatchPersonaDraftApiRequest | None = None,
    draft_id: UUID | None = None,
    group_id: UUID | None = None,
    soft: bool = False,
    accept: bool | None = None,
    idempotency_key: UUID | None = None,
    **kwargs: Any,
) -> PatchPersonaDraftApiResponse:
    """Persona draft using composable infra functions.

    Accepts either a PatchPersonaDraftApiRequest object (from HTTP routes)
    or kwargs directly (from AI generation read path).

    Lifecycle via soft + accept:
      - soft=True: creates dormant draft (connections active=false), skips refresh
      - accept=True: promotes dormant draft (ON CONFLICT upsert → active=true)
      - accept=False: no-op (dormant connections stay for reference)
      - neither: normal create (current behavior)

    Flow:
      1. resolve_profile_identity_context → role
      2. compute_can_draft → permission check
      3. Value resolution (creatable resources only)
      4. create_persona_draft entry tool (idempotent upsert)
      5. Build form state (server is source of truth)
      6. refresh_persona_drafts MV (skipped when soft=True)
      7. invalidate_tags (skipped when soft=True)
    """
    # ── Merge ack fields from request (HTTP) or params (generation pipeline)
    if request is not None:
        idempotency_key = idempotency_key or request.idempotency_key
        if idempotency_key and accept is None:
            accept = request.accept

    # ── Short-circuit: ack path ───────────────────────────────────────
    if accept is not None and idempotency_key is not None:
        if accept:
            async with pool.acquire() as conn:
                drafts = await get_persona_drafts(conn, [idempotency_key])
                async with conn.transaction():
                    if drafts:
                        draft = drafts[0]
                        await create_persona_draft(
                            conn,
                            session_id=session_id,
                            id=idempotency_key,
                            soft=False,
                            name_ids=draft.name_ids,
                            description_ids=draft.description_ids,
                            color_ids=draft.color_ids,
                            icon_ids=draft.icon_ids,
                            instruction_ids=draft.instruction_ids,
                            flag_ids=draft.flag_ids,
                            department_ids=draft.department_ids,
                            parameter_field_ids=draft.parameter_field_ids,
                            example_ids=draft.example_ids,
                            voice_ids=draft.voice_ids,
                            profile_ids=draft.profile_ids or [profile.profiles_id],
                            pending_ids=set(),
                        )
                    else:
                        await create_persona_draft(
                            conn,
                            session_id=session_id,
                            id=idempotency_key,
                            soft=False,
                            profile_ids=[profile.profiles_id],
                        )
            await refresh_persona_impl(
                pool, redis, profile_id=profile_id, session_id=session_id,
                targets=["persona_drafts_mv"], operation_key=idempotency_key,
            )
        # accept=False: no-op (dormant connections stay for reference)
        return PatchPersonaDraftApiResponse(
            success=True,
            draft_id=idempotency_key,
            idempotency_key=idempotency_key,
            message="Draft accepted" if accept else "Draft rejected",
            form_state=DraftFormState(),
        )

    # Build request from kwargs if not provided directly
    if request is None:
        from app.infra.tools.sanitize import sanitize_model_kwargs

        filtered = sanitize_model_kwargs(
            kwargs,
            list_fields={
                "examples", "example_ids", "department_ids", "departments",
                "parameter_field_ids", "parameter_fields", "voice_ids", "voices",
                "flag_ids",
            },
            bool_fields={"active"},
            drop_false_bools={"active"},
            value_id_pairs=[
                ("name", "name_id"), ("description", "description_id"),
                ("color", "color_id"), ("icon", "icon_id"),
                ("instructions", "instructions_id"),
            ],
        )
        if draft_id:
            filtered["draft_id"] = draft_id

        request = PatchPersonaDraftApiRequest(**filtered)

    # ── Step 1: Profile context ────────────────────────────────────────

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

    # ── Step 2: Permission check ───────────────────────────────────────

    if not compute_can_draft(role_level=profile.role_level, role_permissions=profile.role_permissions):
        raise HTTPException(
            status_code=403,
            detail="You don't have permission to create or edit persona drafts.",
        )

    # ── Step 3: Value resolution (search → create if not found) ────────

    from app.infra.persona.permissions_context import resolve_persona_values
    errors = await resolve_persona_values(pool, redis, request)
    if errors:
        raise HTTPException(
            status_code=400,
            detail=[e.model_dump() for e in errors],
        )

    # ── Step 4: Create draft entry (idempotent upsert) ──────────────────

    async with pool.acquire() as conn:
        async with conn.transaction():
            result = await create_persona_draft(
                conn,
                session_id=session_id,
                id=idempotency_key,
                soft=soft,
                name_ids=[request.name_id] if request.name_id else None,
                description_ids=[request.description_id]
                if request.description_id
                else None,
                color_ids=[request.color_id] if request.color_id else None,
                icon_ids=[request.icon_id] if request.icon_id else None,
                instruction_ids=[request.instructions_id]
                if request.instructions_id
                else None,
                flag_ids=list(request.flag_ids) if request.flag_ids else None,
                department_ids=request.department_ids,
                parameter_field_ids=request.parameter_field_ids,
                example_ids=request.example_ids,
                voice_ids=request.voice_ids,
                pending_ids=set(request.pending_ids) if request.pending_ids else None,
                profile_ids=[profile.profiles_id],
            )

    # ── Step 5: Build form state (server is source of truth) ──────────

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
            if rtype == "persona_active":
                echoed_active = rval

    form_state = DraftFormState(
        name_id=request.name_id,
        name=request.name,
        description_id=request.description_id,
        description=request.description,
        instructions_id=request.instructions_id,
        instructions=request.instructions,
        color_id=request.color_id,
        color=request.color,
        icon_id=request.icon_id,
        icon=request.icon,
        flag_ids=list(request.flag_ids or []),
        active=echoed_active,
        department_ids=request.department_ids or [],
        example_ids=request.example_ids or [],
        parameter_field_ids=request.parameter_field_ids or [],
        voice_ids=request.voice_ids or [],
    )

    # ── Step 6+7: Refresh MV + invalidate cache (via canonical refresh) ─

    await refresh_persona_impl(
        pool, redis, profile_id=profile_id, session_id=session_id,
        targets=["persona_drafts_mv"], soft=soft,
        operation_key=idempotency_key or result.id,
    )

    return PatchPersonaDraftApiResponse(
        success=True,
        draft_id=result.id,
        idempotency_key=result.id,
        message="Draft created (pending acceptance)" if soft else "Draft created successfully",
        form_state=form_state,
    )
