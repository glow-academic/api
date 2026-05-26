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
from app.infra.persona.refresh import refresh_persona_impl
from app.infra.server_timing import timed
from app.infra.persona.types import (
    DraftFormState,
    PatchPersonaDraftApiRequest,
    PatchPersonaDraftApiResponse,
    SavePersonaFieldError,
)
from app.infra.profile_identity_context import resolve_profile_identity_context
from app.tools.entries.persona_drafts.create import create_persona_draft
from app.tools.entries.persona_drafts.get import get_persona_drafts
from app.tools.entries.soft_calls.create import create_soft_call
from app.tools.entries.soft_calls.get import get_soft_call
from app.tools.entries.soft_calls.search import search_soft_calls

ARTIFACT = "persona"
OPERATION = "draft"


async def _maybe_auto_accept_draft(
    pool: asyncpg.Pool,
    redis: Redis,
    *,
    draft_id: UUID,
    session_id: UUID,
    profile_ids: list[UUID],
) -> bool:
    """Merge step — auto-accept the draft when no pending fields remain.

    Runs after every patch on a draft. The rule (see project_*_ack
    discussion):

      - pending_*_ids non-empty on the draft → no-op (still resolving)
      - pending_*_ids all empty AND a pending soft_calls_entry exists
        for this draft → append 'accepted' ledger row + flip draft
        active=true. Whether each individual field was accepted or
        rejected per-field doesn't matter; the user processed them.

    There's no implicit reject — that path is only taken via explicit
    wholesale ✗ on the chat panel (handled in the ack short-circuit).

    Returns True if auto-accept fired. Black-box throughout.
    """
    # 1. Locate the pending ledger entry, if any.
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

    # 2. Read current draft state via the canonical get and check
    #    every pending_*_ids list. Any non-empty list means the user
    #    still has decisions to make.
    async with pool.acquire() as conn:
        drafts = await get_persona_drafts(conn, [draft_id], redis, active=None)
    if not drafts:
        return False
    draft = drafts[0]
    if (
        draft.pending_color_ids
        or draft.pending_department_ids
        or draft.pending_description_ids
        or draft.pending_example_ids
        or draft.pending_flag_ids
        or draft.pending_icon_ids
        or draft.pending_instruction_ids
        or draft.pending_name_ids
        or draft.pending_parameter_field_ids
        or draft.pending_voice_ids
    ):
        return False

    # 3. All decisions in. Promote the draft (active=true) and append
    #    the 'accepted' ledger row.
    async with pool.acquire() as conn:
        async with conn.transaction():
            await create_persona_draft(
                conn,
                redis, session_id=session_id,
                id=draft_id,
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
    return True
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
            fields_list = await get_fields(pool, field_ids_list, redis)
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
    # idempotency_key here is the originating tool call's
    # ``calls_entry.id``. The ledger holds (operation='draft',
    # artifact_id=<draft_id>). Resolve draft_id then promote/reject.
    if accept is not None and idempotency_key is not None:
        async with pool.acquire() as conn:
            entry = await get_soft_call(conn, idempotency_key, redis, artifact=ARTIFACT)
        if entry is None or entry.status != "pending" or entry.operation != OPERATION:
            raise HTTPException(
                status_code=404,
                detail="No pending persona draft for this call.",
            )
        target_id = entry.artifact_id

        if accept:
            async with pool.acquire() as conn:
                # active=None so we find the dormant draft (active=false)
                # we're about to promote.
                drafts = await get_persona_drafts(conn, [target_id], redis, active=None)
                async with conn.transaction():
                    if drafts:
                        draft = drafts[0]
                        await create_persona_draft(
                            conn,
                            redis, session_id=session_id,
                            id=target_id,
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
                            redis, session_id=session_id,
                            id=target_id,
                            soft=False,
                            profile_ids=[profile.profiles_id],
                        )
        # accept=False: dormant draft connections stay; the 'rejected'
        # ledger row is the canonical record.

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
        await refresh_persona_impl(
            pool, redis, profile_id=profile_id, session_id=session_id,
            targets=["persona_drafts_mv", "soft_calls_mv"],
        )
        return PatchPersonaDraftApiResponse(
            success=True,
            draft_id=target_id,
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

    # ── Step 2: Permission check ───────────────────────────────────────

    with timed("permissions"):
        if not compute_can_draft(role_level=profile.role_level, role_permissions=profile.role_permissions):
            raise HTTPException(
                status_code=403,
                detail="You don't have permission to create or edit persona drafts.",
            )

    # ── Step 3: Value resolution (search → create if not found) ────────

    with timed("resolve_values"):
        from app.infra.persona.permissions_context import resolve_persona_values
        errors = await resolve_persona_values(pool, redis, request)
        if errors:
            raise HTTPException(
                status_code=400,
                detail=[e.model_dump() for e in errors],
            )

    # ── Step 4: Create draft entry (idempotent upsert) ──────────────────

    with timed("db_write"):
        async with pool.acquire() as conn:
            async with conn.transaction():
                result = await create_persona_draft(
                    conn,
                    redis, session_id=session_id,
                    id=idempotency_key,
                    soft=soft,
                    name=request.name or "",
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

                # Soft-write: append the pending ledger row in the same txn
                # so ack lookups can resolve (artifact, operation, draft_id).
                # idempotency_key here is the calls_entry.id (see
                # execute_infra_operation).
                if soft and idempotency_key is not None:
                    await create_soft_call(
                        conn,
                        redis,
                        call_id=idempotency_key,
                        artifact=ARTIFACT,
                        operation=OPERATION,
                        artifact_id=result.id,
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

    # ── Step 6: Merge step — auto-accept the draft if every pending
    # field is now resolved. Idempotent: the helper short-circuits when
    # any pending_*_ids list is non-empty or no pending ledger exists
    # for this draft. Runs on every patch (including soft creates) so
    # the moment a user clears the last pending field via per-field
    # accept/reject, the draft transitions to 'accepted' without an
    # explicit wholesale ✓.
    auto_accepted = False
    if not soft:
        with timed("auto_accept"):
            auto_accepted = await _maybe_auto_accept_draft(
                pool, redis,
                draft_id=result.id,
                session_id=session_id,
                profile_ids=[profile.profiles_id],
            )

    # ── Step 7: Refresh persona_drafts MV + soft_calls_mv (async enqueue)

    with timed("refresh"):
        await refresh_persona_impl(
            pool, redis, profile_id=profile_id, session_id=session_id,
            targets=["persona_drafts_mv", "soft_calls_mv"],
        )

    if auto_accepted:
        message = "Draft accepted (all fields resolved)"
    elif soft:
        message = "Draft created (pending acceptance)"
    else:
        message = "Draft created successfully"

    return PatchPersonaDraftApiResponse(
        success=True,
        draft_id=result.id,
        idempotency_key=result.id,
        message=message,
        form_state=form_state,
    )
