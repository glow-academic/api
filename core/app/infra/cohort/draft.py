"""Cohort draft logic — composable infra architecture.

This is the closest safe cohort equivalent to the persona draft flow.
It uses only existing black-box tools and keeps the behavior limited to
what the cohort draft entry tool currently supports:
  1. resolve_profile_identity_context — profile (role, departments)
  2. compute_can_draft — permission check
  3. Value resolution
     - creatable: name, description (search first, then create)
     - matchable: flags, departments, simulations, profiles (exact match)
     - compound creatables: simulation_positions, simulation_availability,
       profile_personas
  4. create_cohort_draft — entry tool (append-only snapshot)
  5. Build form state (server is source of truth)
  6. refresh_cohort_impl — canonical refresh path
"""

from __future__ import annotations

from typing import Any
from uuid import UUID

import asyncpg
from fastapi import HTTPException
from redis.asyncio import Redis

from app.infra.cohort.permissions import compute_can_draft
from app.infra.cohort.refresh import refresh_cohort_impl
from app.infra.drafts.ownership import enforce_draft_owner
from app.infra.cohort.types import (
    CohortDraftFormState,
    PatchCohortDraftApiRequest,
    PatchCohortDraftApiResponse,
    SaveCohortFieldError,
)
from app.infra.profile_identity_context import resolve_profile_identity_context
from app.infra.server_timing import timed
from app.infra.tools.sanitize import sanitize_model_kwargs
from app.tools.entries.cohort_drafts.create import create_cohort_draft
from app.tools.entries.cohort_drafts.get import get_cohort_drafts
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
from app.tools.resources.profile_personas.create import create_profile_persona
from app.tools.resources.profiles.search import search_profiles
from app.tools.resources.simulation_availability.create import (
    create_simulation_availability,
)
from app.tools.resources.simulation_positions.create import (
    create_simulation_position as create_sim_position,
)
from app.tools.resources.simulations.search import search_simulations
from app.utils.cache.hedged_row import transaction_with_writeback

ARTIFACT = "cohort"
OPERATION = "draft"


async def _maybe_auto_accept_cohort_draft(
    pool: asyncpg.Pool,
    redis: Redis,
    *,
    draft_id: UUID,
    session_id: UUID,
    profile_ids: list[UUID],
) -> bool:
    """Auto-accept a cohort draft when no pending fields remain."""
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
        drafts = await get_cohort_drafts(conn, [draft_id], redis, active=None)
    if not drafts:
        return False
    draft = drafts[0]
    if (
        draft.pending_department_ids
        or draft.pending_description_ids
        or draft.pending_flag_ids
        or draft.pending_name_ids
        or draft.pending_profile_persona_ids
        or draft.pending_profile_ids
        or draft.pending_simulation_availability_ids
        or draft.pending_simulation_position_ids
        or draft.pending_simulation_ids
    ):
        return False

    async with pool.acquire() as conn:
        async with transaction_with_writeback(conn):
            await create_cohort_draft(
                conn,
                redis, session_id=session_id,
                id=draft_id,
                soft=False,
                department_ids=draft.department_ids,
                description_ids=draft.description_ids,
                flag_ids=draft.flag_ids,
                name_ids=draft.name_ids,
                profile_persona_ids=draft.profile_persona_ids,
                simulation_availability_ids=draft.simulation_availability_ids,
                simulation_position_ids=draft.simulation_position_ids,
                simulation_ids=draft.simulation_ids,
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


def _resolve_many_ids(
    results: list[Any],
    raw_values: list[str],
    *,
    field: str,
    label: str,
    attr: str = "name",
) -> tuple[list[UUID] | None, list[SaveCohortFieldError]]:
    lookup: dict[str, UUID] = {}
    for item in results:
        value = getattr(item, attr, None)
        item_id = getattr(item, "id", None)
        if isinstance(value, str) and item_id:
            lookup.setdefault(value.lower(), item_id)

    resolved_ids: list[UUID] = []
    errors: list[SaveCohortFieldError] = []
    for raw_value in raw_values:
        match_id = lookup.get(raw_value.strip().lower())
        if match_id is None:
            errors.append(
                SaveCohortFieldError(
                    field=field,
                    message=f'{label} "{raw_value}" not found',
                )
            )
            continue
        resolved_ids.append(match_id)

    if errors:
        return None, errors
    return resolved_ids, []


async def _resolve_creatable_values(
    pool: asyncpg.Pool,
    redis: Redis,
    request: PatchCohortDraftApiRequest,
) -> list[SaveCohortFieldError]:
    """Resolve raw value fields to resource IDs (mutates request in place)."""
    errors: list[SaveCohortFieldError] = []

    async with pool.acquire() as conn:
        # ------------------------------------------------------------------
        # Creatable single-selects: search first, then create.
        # ------------------------------------------------------------------

        if getattr(request, "name", None) is not None and getattr(request, "name_id", None) is None:
            name = request.name
            assert name is not None
            results = await search_names(
                conn,
                redis,
                search=name,
                limit_count=20,
                cohort=True,
            )
            match_id = _exact_match_id(results, name)
            if match_id is None:
                result = await create_name(conn, name, redis)
                match_id = result.id
            request.name_id = match_id

        if (
            getattr(request, "description", None) is not None
            and getattr(request, "description_id", None) is None
        ):
            description = request.description
            assert description is not None
            results = await search_descriptions(
                conn,
                redis,
                search=description,
                limit_count=20,
                cohort=True,
            )
            match_id = _exact_match_id(results, description, attr="description")
            if match_id is None:
                result = await create_description(conn, description, redis)
                match_id = result.id
            request.description_id = match_id

        # ------------------------------------------------------------------
        # Resolve denormalized flag boolean (`active`) → canonical flag_ids
        # entry via (type, value) lookup in flags_resource. Existing
        # flag_ids are preserved verbatim; the derived id is merged in.
        # ------------------------------------------------------------------
        denorm_flag_values: dict[str, bool] = {}
        if getattr(request, "active", None) is not None:
            denorm_flag_values["cohort_active"] = bool(request.active)
        if denorm_flag_values:
            all_flags = await search_flags(
                conn,
                redis,
                search=None,
                limit_count=200,
                bypass_cache=True,
            )
            resolved_flag_ids: list[UUID] = list(request.flag_ids or [])
            seen = set(resolved_flag_ids)
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
                if match and match.id and match.id not in seen:
                    resolved_flag_ids.append(match.id)
                    seen.add(match.id)
                elif not match:
                    errors.append(
                        SaveCohortFieldError(
                            field=flag_type,
                            message=(
                                f"Flag row not found for type={flag_type} "
                                f"value={desired_value}"
                            ),
                        )
                    )
            request.flag_ids = resolved_flag_ids

        if getattr(request, "departments", None) is not None and getattr(request, "department_ids", None) is None:
            department_values = request.departments or []
            all_departments = await search_departments(
                conn,
                redis,
                search=None,
                limit_count=1000,
                cohort=True,
            )
            resolved_ids, field_errors = _resolve_many_ids(
                all_departments,
                department_values,
                field="departments",
                label="Department",
            )
            errors.extend(field_errors)
            if resolved_ids is not None:
                request.department_ids = resolved_ids

        if getattr(request, "simulations", None) is not None and getattr(request, "simulation_ids", None) is None:
            simulation_values = request.simulations or []
            all_simulations = await search_simulations(
                conn,
                redis,
                search=None,
                limit_count=1000,
                cohort=True,
            )
            resolved_ids, field_errors = _resolve_many_ids(
                all_simulations,
                simulation_values,
                field="simulations",
                label="Simulation",
            )
            errors.extend(field_errors)
            if resolved_ids is not None:
                request.simulation_ids = resolved_ids

        if getattr(request, "profiles", None) is not None and getattr(request, "profile_ids", None) is None:
            profile_values = request.profiles or []
            all_profiles = await search_profiles(
                conn,
                redis,
                search=None,
                limit_count=1000,
                cohort=True,
            )
            resolved_ids, field_errors = _resolve_many_ids(
                all_profiles,
                profile_values,
                field="profiles",
                label="Profile",
            )
            errors.extend(field_errors)
            if resolved_ids is not None:
                request.profile_ids = resolved_ids

        # ------------------------------------------------------------------
        # Compound creatables: preserve existing create support.
        # ------------------------------------------------------------------

        if request.simulation_positions:
            created_ids: list[UUID] = []
            for sp in request.simulation_positions:
                result = await create_sim_position(
                    conn,
                    sp.simulation_id,
                    sp.value,
                    redis,
                )
                created_ids.append(result.id)
            request.simulation_position_ids = (request.simulation_position_ids or []) + created_ids

        if request.simulation_availability:
            created_ids = []
            for sa in request.simulation_availability:
                result = await create_simulation_availability(
                    conn,
                    sa.simulation_id,
                    sa.time,
                    sa.type,
                    redis,
                )
                created_ids.append(result.id)
            request.simulation_availability_ids = (
                request.simulation_availability_ids or []
            ) + created_ids

        if request.profile_personas:
            created_ids = []
            for pp in request.profile_personas:
                result = await create_profile_persona(
                    conn,
                    pp.profile_id,
                    pp.persona_id,
                    redis,
                )
                created_ids.append(result.id)
            request.profile_persona_ids = (request.profile_persona_ids or []) + created_ids

    return errors


async def patch_cohort_draft_impl(
    pool: asyncpg.Pool,
    redis: Redis,
    *,
    profile_id: UUID,
    session_id: UUID,
    request: PatchCohortDraftApiRequest | None = None,
    soft: bool = False,
    accept: bool | None = None,
    idempotency_key: UUID | None = None,
    **kwargs: Any,
) -> PatchCohortDraftApiResponse:
    """Cohort draft using composable infra functions."""

    # ------------------------------------------------------------------
    # Merge ack fields from request (HTTP) or params (generation pipeline).
    # ------------------------------------------------------------------
    if request is not None:
        idempotency_key = idempotency_key or request.idempotency_key
        if idempotency_key and accept is None:
            accept = request.accept

    # ------------------------------------------------------------------
    # Profile context — resolved BEFORE the ack short-circuit so the ack
    # branch can use ``profile.profiles_id`` (the canonical pattern that
    # persona uses; cohort previously had a NameError waiting to happen).
    # ------------------------------------------------------------------
    with timed("profile"):
        profile = await resolve_profile_identity_context(
            pool, profile_id, redis, session_id=session_id,
        )
    if profile is None:
        raise HTTPException(
            status_code=401,
            detail="Profile not found. Please sign in again.",
        )

    # ------------------------------------------------------------------
    # Ack short-circuit.
    # ------------------------------------------------------------------
    if accept is not None and idempotency_key is not None:
        async with pool.acquire() as conn:
            entry = await get_soft_call(conn, idempotency_key, redis, artifact=ARTIFACT)
        if entry is None or entry.status != "pending" or entry.operation != OPERATION:
            raise HTTPException(
                status_code=404,
                detail="No pending cohort draft for this call.",
            )
        target_id = entry.artifact_id

        if accept:
            async with pool.acquire() as conn:
                await enforce_draft_owner(
                    conn,
                    redis,
                    draft_id=target_id,
                    getter=get_cohort_drafts,
                    caller_session_id=session_id,
                    caller_profile_id=profile.profiles_id,
                    role_level=profile.role_level,
                    artifact=ARTIFACT,
                )
                drafts = await get_cohort_drafts(conn, [target_id], redis, active=None)
                async with transaction_with_writeback(conn):
                    if drafts:
                        draft = drafts[0]
                        await create_cohort_draft(
                            conn,
                            redis, session_id=session_id,
                            id=target_id,
                            soft=False,
                            department_ids=draft.department_ids,
                            description_ids=draft.description_ids,
                            flag_ids=draft.flag_ids,
                            name_ids=draft.name_ids,
                            profile_persona_ids=draft.profile_persona_ids,
                            simulation_availability_ids=draft.simulation_availability_ids,
                            simulation_position_ids=draft.simulation_position_ids,
                            simulation_ids=draft.simulation_ids,
                            profile_ids=draft.profile_ids or [profile.profiles_id],
                            pending_ids=set(),
                        )
                    else:
                        await create_cohort_draft(
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

        await refresh_cohort_impl(
            pool,
            redis,
            profile_id=profile_id,
            session_id=session_id,
            targets=["cohort_drafts_mv"],
            operation_key=idempotency_key,
        )
        return PatchCohortDraftApiResponse(
            success=True,
            draft_id=target_id,
            idempotency_key=idempotency_key,
            message="Draft accepted" if accept else "Draft rejected",
            form_state=CohortDraftFormState(),
        )

    # Build request from kwargs if not provided directly.
    if request is None:
        filtered = sanitize_model_kwargs(
            kwargs,
            list_fields={
                "flag_ids",
                "department_ids",
                "departments",
                "simulation_ids",
                "simulations",
                "profile_ids",
                "profiles",
                "simulation_position_ids",
                "simulation_positions",
                "simulation_availability_ids",
                "simulation_availability",
                "profile_persona_ids",
                "profile_personas",
                "pending_ids",
            },
            bool_fields={"active"},
            value_id_pairs=[
                ("name", "name_id"),
                ("description", "description_id"),
            ],
        )
        if idempotency_key is not None and "idempotency_key" not in filtered:
            filtered["idempotency_key"] = idempotency_key
        if accept is not None and "accept" not in filtered:
            filtered["accept"] = accept
        request = PatchCohortDraftApiRequest(**filtered)

    # Step 1: Profile context — already resolved at top.

    # ------------------------------------------------------------------
    # Step 2: Permission check
    # ------------------------------------------------------------------
    with timed("permissions"):
        if not compute_can_draft(
            role_level=profile.role_level,
            role_permissions=profile.role_permissions,
        ):
            raise HTTPException(
                status_code=403,
                detail="You don't have permission to create or edit cohort drafts.",
            )

    # ------------------------------------------------------------------
    # Step 3: Value resolution
    # ------------------------------------------------------------------
    with timed("resolve_values"):
        errors = await _resolve_creatable_values(pool, redis, request)
    if errors:
        raise HTTPException(
            status_code=400,
            detail=[error.model_dump() for error in errors],
        )

    # ------------------------------------------------------------------
    # Step 4: Create draft entry
    # ------------------------------------------------------------------
    resolved_pending_ids = list(getattr(request, "pending_ids", None) or [])
    resolved_flag_ids = list(request.flag_ids or [])
    with timed("db_write"):
     async with pool.acquire() as conn:
        await enforce_draft_owner(
            conn,
            redis,
            draft_id=idempotency_key,
            getter=get_cohort_drafts,
            caller_session_id=session_id,
            caller_profile_id=profile.profiles_id,
            role_level=profile.role_level,
            artifact=ARTIFACT,
        )
        async with transaction_with_writeback(conn):
            result = await create_cohort_draft(
                conn,
                redis, session_id=session_id,
                id=idempotency_key,
                soft=soft,
                name=request.name or "",
                department_ids=request.department_ids,
                description_ids=[request.description_id]
                if request.description_id
                else None,
                flag_ids=resolved_flag_ids or None,
                name_ids=[request.name_id] if request.name_id else None,
                profile_persona_ids=request.profile_persona_ids,
                profile_ids=list(dict.fromkeys((request.profile_ids or []) + [profile.profiles_id])),
                simulation_availability_ids=request.simulation_availability_ids,
                simulation_position_ids=request.simulation_position_ids,
                simulation_ids=request.simulation_ids,
                pending_ids=set(resolved_pending_ids) if resolved_pending_ids else None,
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
        await _maybe_auto_accept_cohort_draft(
            pool, redis,
            draft_id=result.id,
            session_id=session_id,
            profile_ids=[profile.profiles_id],
        )

    # ------------------------------------------------------------------
    # Step 5: Build form state (server is source of truth)
    # Re-derive denormalized booleans from final flag_ids so the client
    # echo matches whatever the server actually persisted.
    # ------------------------------------------------------------------
    echoed_active: bool | None = getattr(request, "active", None)
    if resolved_flag_ids:
        async with pool.acquire() as conn:
            flag_rows = await search_flags(
                conn,
                redis,
                search=None,
                limit_count=200,
                bypass_cache=True,
            )
        rows_by_id = {row.id: row for row in flag_rows if getattr(row, "id", None)}
        for fid in resolved_flag_ids:
            row = rows_by_id.get(fid)
            if not row:
                continue
            rtype = getattr(row, "type", None) or getattr(row, "name", None)
            if rtype == "cohort_active":
                echoed_active = getattr(row, "value", None)

    form_state = CohortDraftFormState(
        name_id=request.name_id,
        name=getattr(request, "name", None),
        description_id=request.description_id,
        description=getattr(request, "description", None),
        flag_ids=resolved_flag_ids,
        active=echoed_active,
        department_ids=request.department_ids or [],
        departments=getattr(request, "departments", None) or [],
        simulation_ids=request.simulation_ids or [],
        simulations=getattr(request, "simulations", None) or [],
        profile_ids=request.profile_ids or [],
        profiles=getattr(request, "profiles", None) or [],
        simulation_position_ids=request.simulation_position_ids or [],
        simulation_positions=request.simulation_positions or [],
        simulation_availability_ids=request.simulation_availability_ids or [],
        simulation_availability=request.simulation_availability or [],
        profile_persona_ids=request.profile_persona_ids or [],
        profile_personas=request.profile_personas or [],
        pending_ids=resolved_pending_ids,
    )

    # ------------------------------------------------------------------
    # Step 6: Refresh MV
    # ------------------------------------------------------------------
    with timed("refresh"):
        await refresh_cohort_impl(
            pool,
            redis,
            profile_id=profile_id,
            session_id=session_id,
            targets=["cohort_drafts_mv"],
            soft=soft,
            name=request.name or "",
            operation_key=idempotency_key or result.id,
        )

    return PatchCohortDraftApiResponse(
        success=True,
        draft_id=result.id,
        idempotency_key=idempotency_key or result.id,
        message="Draft created (pending acceptance)" if soft else "Draft created successfully",
        form_state=form_state,
    )
