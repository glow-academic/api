"""Simulation draft logic — composable infra architecture.

Core draft function that composes existing black-box tools:
  1. resolve_profile_identity_context — profile (role, departments)
  2. compute_can_draft — permission check
  3. Value resolution (creatable resources only) — raw value → ID
  4. create_simulation_draft — entry tool (append-only snapshot)
  5. refresh_simulation_impl — canonical refresh + cache invalidation
  6. Build form state (server is source of truth)
"""

from __future__ import annotations

from typing import Any
from uuid import UUID

import asyncpg
from fastapi import HTTPException
from redis.asyncio import Redis

from app.infra.profile_identity_context import resolve_profile_identity_context
from app.infra.simulation.permissions import compute_can_draft
from app.infra.simulation.refresh import refresh_simulation_impl
from app.infra.server_timing import timed
from app.infra.simulation.types import (
    DraftScenarioFlagDenormValue,
    PatchSimulationDraftApiRequest,
    PatchSimulationDraftApiResponse,
    SaveSimulationFieldError,
    SimulationDraftFormState,
)
from app.infra.tools.sanitize import sanitize_model_kwargs
from app.tools.entries.simulation_drafts.create import (
    create_simulation_draft,
)
from app.tools.entries.simulation_drafts.get import get_simulation_drafts
from app.tools.entries.soft_calls.create import create_soft_call
from app.tools.entries.soft_calls.get import get_soft_call
from app.tools.entries.soft_calls.refresh import refresh_soft_calls
from app.tools.entries.soft_calls.search import search_soft_calls
from app.tools.resources.descriptions.create import create_description
from app.tools.resources.descriptions.search import search_descriptions
from app.tools.resources.flags.search import search_flags
from app.tools.resources.names.create import create_name
from app.tools.resources.names.search import search_names
from app.tools.resources.scenario_flags.create import create_scenario_flag
from app.tools.resources.scenario_flags.get import get_scenario_flags
from app.tools.resources.scenario_positions.create import (
    create_scenario_position,
)
from app.tools.resources.scenario_rubrics.create import create_scenario_rubric
from app.tools.resources.scenario_time_limits.create import (
    create_scenario_time_limit,
)

ARTIFACT = "simulation"
OPERATION = "draft"


async def _maybe_auto_accept_simulation_draft(
    pool: asyncpg.Pool,
    redis: Redis,
    *,
    draft_id: UUID,
    session_id: UUID,
    profile_ids: list[UUID],
) -> bool:
    """Auto-accept the simulation draft when no pending fields remain."""
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
        drafts = await get_simulation_drafts(conn, [draft_id], redis, active=None)
    if not drafts:
        return False
    draft = drafts[0]
    pending_lists = [
        getattr(draft, "pending_name_ids", None),
        getattr(draft, "pending_description_ids", None),
        getattr(draft, "pending_flag_ids", None),
        getattr(draft, "pending_department_ids", None),
        getattr(draft, "pending_scenario_ids", None),
        getattr(draft, "pending_scenario_flag_ids", None),
        getattr(draft, "pending_scenario_position_ids", None),
        getattr(draft, "pending_scenario_rubric_ids", None),
        getattr(draft, "pending_scenario_time_limit_ids", None),
    ]
    if any(pl for pl in pending_lists if pl):
        return False

    async with pool.acquire() as conn:
        async with conn.transaction():
            await create_simulation_draft(
                conn,
                redis, session_id=session_id,
                id=draft_id,
                soft=False,
                name_ids=draft.name_ids,
                description_ids=draft.description_ids,
                flag_ids=draft.flag_ids,
                department_ids=draft.department_ids,
                scenario_ids=draft.scenario_ids,
                scenario_flag_ids=draft.scenario_flag_ids,
                scenario_position_ids=draft.scenario_position_ids,
                scenario_rubric_ids=draft.scenario_rubric_ids,
                scenario_time_limit_ids=draft.scenario_time_limit_ids,
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


# Denormalized bool field name → flag type in flags_resource.
SIMULATION_DENORM_FLAG_FIELDS = {
    "active": "simulation_active",
    "practice": "practice",
}

# ---------------------------------------------------------------------------
# Value resolution — creatable resources only
# ---------------------------------------------------------------------------


async def _resolve_creatable_values(
    pool: asyncpg.Pool,
    redis: Redis,
    request: PatchSimulationDraftApiRequest,
) -> list[SaveSimulationFieldError]:
    """Resolve raw value fields to resource IDs (mutates request in place).

    Single-select creatables: name, description
      → value creates resource, ID replaces value (mutually exclusive).

    Multi-select compound creatables: scenario_flags, scenario_positions,
      scenario_rubrics, scenario_time_limits
      → values create resources, created IDs are merged with existing IDs.

    Returns a list of errors (empty if all resolved).
    """
    errors: list[SaveSimulationFieldError] = []

    async with pool.acquire() as conn:
        # ── Single-select creatables ──────────────────────────────────────

        if request.name is not None and request.name_id is None:
            results = await search_names(conn, redis, search=request.name, limit_count=20)
            match = next(
                (
                    r
                    for r in results
                    if r.name is not None and r.name.lower() == request.name.lower()
                ),
                None,
            )
            if match and match.id:
                request.name_id = match.id
            else:
                result = await create_name(conn, request.name, redis)
                request.name_id = result.id

        if request.description is not None and request.description_id is None:
            results = await search_descriptions(
                conn,
                redis,
                search=request.description,
                limit_count=20,
            )
            match = next(
                (
                    r
                    for r in results
                    if r.description is not None
                    and r.description.lower() == request.description.lower()
                ),
                None,
            )
            if match and match.id:
                request.description_id = match.id
            else:
                result = await create_description(conn, request.description, redis)
                request.description_id = result.id

        # ── Multi-select compound creatables (merged mode) ────────────────

        if request.scenario_flags:
            created_ids = []
            for sf in request.scenario_flags:
                result = await create_scenario_flag(
                    conn, sf.scenario_id, sf.flag_id, redis
                )
                created_ids.append(result.id)
            request.scenario_flag_ids = (request.scenario_flag_ids or []) + created_ids

        # Denormalized scenario_flag_values: (scenario_id, type, value) →
        # resolve to flag_id via flags_resource, then upsert the junction.
        if request.scenario_flag_values:
            all_flag_rows = await search_flags(
                conn, redis, search=None, limit_count=500, bypass_cache=True
            )
            resolved_sf_ids: list[UUID] = list(request.scenario_flag_ids or [])
            seen_sf = set(resolved_sf_ids)
            for entry in request.scenario_flag_values:
                match = next(
                    (
                        f
                        for f in all_flag_rows
                        if (getattr(f, "type", None) == entry.type
                            or getattr(f, "name", None) == entry.type)
                        and getattr(f, "value", None) is entry.value
                    ),
                    None,
                )
                if not (match and match.id):
                    errors.append(
                        SaveSimulationFieldError(
                            field="scenario_flag_values",
                            message=(
                                f"Flag row not found for type={entry.type} "
                                f"value={entry.value}"
                            ),
                        )
                    )
                    continue
                # Upsert the (scenario_id, flag_id) junction row.
                sf_result = await create_scenario_flag(
                    conn, entry.scenario_id, match.id, redis
                )
                if sf_result.id and sf_result.id not in seen_sf:
                    resolved_sf_ids.append(sf_result.id)
                    seen_sf.add(sf_result.id)
            request.scenario_flag_ids = resolved_sf_ids

        if request.scenario_positions:
            created_ids = []
            for sp in request.scenario_positions:
                result = await create_scenario_position(
                    conn, sp.scenario_id, sp.value, redis
                )
                created_ids.append(result.id)
            request.scenario_position_ids = (
                request.scenario_position_ids or []
            ) + created_ids

        if request.scenario_rubrics:
            created_ids = []
            for sr in request.scenario_rubrics:
                result = await create_scenario_rubric(
                    conn, sr.scenario_id, sr.rubric_id, redis
                )
                created_ids.append(result.id)
            request.scenario_rubric_ids = (
                request.scenario_rubric_ids or []
            ) + created_ids

        if request.scenario_time_limits:
            created_ids = []
            for stl in request.scenario_time_limits:
                result = await create_scenario_time_limit(
                    conn,
                    stl.scenario_id,
                    stl.time_limit_seconds,
                    redis,
                    negative=stl.negative,
                )
                created_ids.append(result.id)
            request.scenario_time_limit_ids = (
                request.scenario_time_limit_ids or []
            ) + created_ids

    # Denorm bool → flag_ids via (type, value) lookup in flags_resource.
    denorm_values: dict[str, bool] = {}
    for field_name, flag_type in SIMULATION_DENORM_FLAG_FIELDS.items():
        v = getattr(request, field_name, None)
        if v is not None:
            denorm_values[flag_type] = bool(v)
    if denorm_values:
        async with pool.acquire() as conn:
            all_rows = await search_flags(
                conn, redis, search=None, limit_count=200, bypass_cache=True
            )
        resolved_ids: list[UUID] = list(request.flag_ids or [])
        seen = set(resolved_ids)
        for ftype, desired in denorm_values.items():
            match = next(
                (
                    f
                    for f in all_rows
                    if (getattr(f, "type", None) == ftype
                        or getattr(f, "name", None) == ftype)
                    and getattr(f, "value", None) is desired
                ),
                None,
            )
            if match and match.id and match.id not in seen:
                resolved_ids.append(match.id)
                seen.add(match.id)
        request.flag_ids = resolved_ids

    return errors


# ---------------------------------------------------------------------------
# patch_simulation_draft_impl — composable infra architecture
# ---------------------------------------------------------------------------


async def patch_simulation_draft_impl(
    pool: asyncpg.Pool,
    redis: Redis,
    *,
    profile_id: UUID,
    session_id: UUID,
    request: PatchSimulationDraftApiRequest | None = None,
    draft_id: UUID | None = None,
    soft: bool = False,
    accept: bool | None = None,
    idempotency_key: UUID | None = None,
    **kwargs: Any,
) -> PatchSimulationDraftApiResponse:
    """Simulation draft using composable infra functions.

    Flow:
      1. resolve_profile_identity_context → role
      2. compute_can_draft → permission check
      3. Value resolution (creatable resources only)
      4. create_simulation_draft entry tool (append-only snapshot)
      5. refresh_simulation_impl canonical refresh + cache invalidation
      6. Build form state (server is source of truth)
    """
    # Merge ack fields from request (HTTP) or kwargs (direct callers).
    if request is not None:
        idempotency_key = idempotency_key or getattr(request, "idempotency_key", None)
        if idempotency_key is not None and accept is None:
            accept = getattr(request, "accept", None)

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
        if not compute_can_draft(
            role_level=profile.role_level,
            role_permissions=profile.role_permissions,
        ):
            raise HTTPException(
                status_code=403,
                detail="You don't have permission to create or edit simulation drafts.",
            )

    # ── Short-circuit: ack path ───────────────────────────────────────
    if accept is not None and idempotency_key is not None:
        async with pool.acquire() as conn:
            entry = await get_soft_call(conn, idempotency_key, redis, artifact=ARTIFACT)
        if entry is None or entry.status != "pending" or entry.operation != OPERATION:
            raise HTTPException(
                status_code=404,
                detail="No pending simulation draft for this call.",
            )
        target_id = entry.artifact_id

        if accept:
            async with pool.acquire() as conn:
                drafts = await get_simulation_drafts(conn, [target_id], redis, active=None)
                async with conn.transaction():
                    if drafts:
                        draft = drafts[0]
                        await create_simulation_draft(
                            conn,
                            redis, session_id=session_id,
                            id=target_id,
                            soft=False,
                            name_ids=draft.name_ids,
                            description_ids=draft.description_ids,
                            flag_ids=draft.flag_ids,
                            department_ids=draft.department_ids,
                            scenario_ids=draft.scenario_ids,
                            scenario_flag_ids=draft.scenario_flag_ids,
                            scenario_position_ids=draft.scenario_position_ids,
                            scenario_rubric_ids=draft.scenario_rubric_ids,
                            scenario_time_limit_ids=draft.scenario_time_limit_ids,
                            profile_ids=draft.profile_ids or [profile.profiles_id],
                            pending_ids=set(),
                        )
                    else:
                        await create_simulation_draft(
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

        if accept:
            await refresh_simulation_impl(
                pool,
                redis,
                profile_id=profile_id,
                session_id=session_id,
                targets=["simulation_drafts_mv"],
                operation_key=idempotency_key,
            )
        return PatchSimulationDraftApiResponse(
            success=True,
            draft_id=target_id,
            idempotency_key=idempotency_key,
            message="Draft accepted" if accept else "Draft rejected",
            form_state=SimulationDraftFormState(),
        )

    if request is None:
        filtered = sanitize_model_kwargs(
            kwargs,
            list_fields={
                "flag_ids",
                "department_ids",
                "scenario_ids",
                "scenario_flag_ids",
                "scenario_flags",
                "scenario_flag_values",
                "scenario_position_ids",
                "scenario_positions",
                "scenario_rubric_ids",
                "scenario_rubrics",
                "scenario_time_limit_ids",
                "scenario_time_limits",
            },
            value_id_pairs=[
                ("name", "name_id"),
                ("description", "description_id"),
            ],
        )
        if draft_id is not None:
            filtered["input_draft_id"] = draft_id
        request = PatchSimulationDraftApiRequest(**filtered)

    if draft_id is not None and getattr(request, "input_draft_id", None) is None:
        request.input_draft_id = draft_id
    if draft_id is not None and getattr(request, "draft_id", None) is None:
        request.draft_id = draft_id
    if (
        getattr(request, "draft_id", None) is not None
        and getattr(request, "input_draft_id", None) is None
    ):
        request.input_draft_id = request.draft_id

    # ── Step 3: Value resolution (creatable only) ──────────────────────

    with timed("resolve_values"):
        errors = await _resolve_creatable_values(pool, redis, request)
    if errors:
        raise HTTPException(
            status_code=400,
            detail=[e.model_dump() for e in errors],
        )

    # ── Step 4: Create draft entry (append-only snapshot) ──────────────

    with timed("db_write"):
      async with pool.acquire() as conn:
        async with conn.transaction():
            result = await create_simulation_draft(
                conn,
                redis, session_id=session_id,
                id=idempotency_key,
                soft=soft,
                name=request.name or "",
                name_ids=[request.name_id] if request.name_id else None,
                description_ids=[request.description_id]
                if request.description_id
                else None,
                flag_ids=request.flag_ids,
                department_ids=request.department_ids,
                scenario_ids=request.scenario_ids,
                scenario_flag_ids=request.scenario_flag_ids,
                scenario_position_ids=request.scenario_position_ids,
                scenario_rubric_ids=request.scenario_rubric_ids,
                scenario_time_limit_ids=request.scenario_time_limit_ids,
                profile_ids=[profile.profiles_id],
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

    if soft and idempotency_key is not None:
        async with pool.acquire() as conn:
            await refresh_soft_calls(conn)

    if not soft:
        await _maybe_auto_accept_simulation_draft(
            pool, redis,
            draft_id=result.id,
            session_id=session_id,
            profile_ids=[profile.profiles_id],
        )

    # ── Step 5: Canonical refresh ──────────────────────────────────────

    with timed("refresh"):
        await refresh_simulation_impl(
            pool,
            redis,
            profile_id=profile_id,
            session_id=session_id,
            targets=["simulation_drafts_mv"],
            soft=soft,
            name=request.name or "",
            operation_key=idempotency_key or result.id,
        )

    # ── Step 6: Build form state (server is source of truth) ──────────

    # Re-derive denorm bools from final flag_ids so client echo matches
    # what the server actually persisted.
    echoed_bools: dict[str, bool | None] = {
        f: getattr(request, f, None) for f in SIMULATION_DENORM_FLAG_FIELDS
    }
    if request.flag_ids:
        async with pool.acquire() as conn:
            flag_rows = await search_flags(
                conn, redis, search=None, limit_count=200, bypass_cache=True
            )
        rows_by_id = {row.id: row for row in flag_rows if getattr(row, "id", None)}
        type_to_field = {v: k for k, v in SIMULATION_DENORM_FLAG_FIELDS.items()}
        for fid in request.flag_ids:
            row = rows_by_id.get(fid)
            if not row:
                continue
            rtype = getattr(row, "type", None) or getattr(row, "name", None)
            field = type_to_field.get(rtype or "")
            if field:
                echoed_bools[field] = getattr(row, "value", None)

    # Echo scenario_flag_values from the final scenario_flag_ids: look up
    # each junction row → flag_id → flags_resource (type, value).
    scenario_flag_values_echo: list[DraftScenarioFlagDenormValue] = []
    if request.scenario_flag_ids:
        async with pool.acquire() as conn:
            sf_rows = await get_scenario_flags(
                conn, list(request.scenario_flag_ids), redis, bypass_cache=True
            )
            flag_rows = await search_flags(
                conn, redis, search=None, limit_count=500, bypass_cache=True
            )
        flag_by_id = {row.id: row for row in flag_rows if getattr(row, "id", None)}
        for sf_row in sf_rows:
            flag_id = getattr(sf_row, "flag_id", None)
            scenario_id = getattr(sf_row, "scenario_id", None)
            if not (flag_id and scenario_id):
                continue
            fr = flag_by_id.get(flag_id)
            if not fr:
                continue
            ftype = getattr(fr, "type", None) or getattr(fr, "name", None)
            fval = getattr(fr, "value", None)
            if ftype is None or fval is None:
                continue
            scenario_flag_values_echo.append(
                DraftScenarioFlagDenormValue(
                    scenario_id=scenario_id, type=ftype, value=bool(fval)
                )
            )

    form_state = SimulationDraftFormState(
        name_id=request.name_id,
        name=request.name,
        description_id=request.description_id,
        description=request.description,
        flag_ids=request.flag_ids or [],
        active=echoed_bools.get("active"),
        practice=echoed_bools.get("practice"),
        department_ids=request.department_ids or [],
        scenario_ids=request.scenario_ids or [],
        scenario_flag_ids=request.scenario_flag_ids or [],
        scenario_flag_values=scenario_flag_values_echo,
        scenario_position_ids=request.scenario_position_ids or [],
        scenario_rubric_ids=request.scenario_rubric_ids or [],
        scenario_time_limit_ids=request.scenario_time_limit_ids or [],
        pending_ids=request.pending_ids or [],
    )

    response_idempotency_key = idempotency_key or result.id

    return PatchSimulationDraftApiResponse(
        success=True,
        draft_id=result.id,
        idempotency_key=response_idempotency_key,
        message="Draft created (pending acceptance)" if soft else "Draft created successfully",
        form_state=form_state,
    )
