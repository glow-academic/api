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
from app.tools.entries.persona_drafts.refresh import refresh_persona_drafts
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
from app.utils.cache.invalidate_tags import invalidate_tags

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

    if request.active_flag is not None and request.active_flag_id is None:
        async with pool.acquire() as conn:
            results = await search_flags(
                conn,
                redis,
                search=None,
                flag_type="persona_active",
                limit_count=100,
            )
        match = next((r for r in results if r.type == "persona_active"), None)
        if match and match.id:
            if request.active_flag:
                request.active_flag_id = match.id
        elif request.active_flag:
            errors.append(
                SavePersonaFieldError(
                    field="active_flag", message="Active flag resource not found"
                )
            )

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
    # Build request from kwargs if not provided directly
    if request is None:
        from app.infra.tools.sanitize import sanitize_model_kwargs

        filtered = sanitize_model_kwargs(
            kwargs,
            list_fields={
                "examples", "example_ids", "department_ids", "departments",
                "parameter_field_ids", "parameter_fields", "voice_ids", "voices",
            },
            bool_fields={"active_flag"},
            drop_false_bools={"active_flag"},
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
                flag_ids=[request.active_flag_id] if request.active_flag_id else None,
                department_ids=request.department_ids,
                parameter_field_ids=request.parameter_field_ids,
                example_ids=request.example_ids,
                voice_ids=request.voice_ids,
                pending_ids=set(request.pending_ids) if request.pending_ids else None,
            )

    # ── Step 5: Build form state (server is source of truth) ──────────

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
        active_flag_id=request.active_flag_id,
        department_ids=request.department_ids or [],
        example_ids=request.example_ids or [],
        parameter_field_ids=request.parameter_field_ids or [],
        voice_ids=request.voice_ids or [],
    )

    # ── Step 6: Refresh MV (skip when soft — dormant draft) ───────────

    if not soft:
        async with pool.acquire() as conn:
            await refresh_persona_drafts(conn)

    # ── Step 7: Invalidate cache (skip when soft) ─────────────────────

    if not soft:
        await invalidate_tags(["personas", "drafts"], redis=redis)

    return PatchPersonaDraftApiResponse(
        success=True,
        draft_id=result.id,
        idempotency_key=result.id,
        message="Draft created (pending acceptance)" if soft else "Draft created successfully",
        form_state=form_state,
    )
