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
from app.infra.cohort.types import (
    CohortDraftFormState,
    PatchCohortDraftApiRequest,
    PatchCohortDraftApiResponse,
    SaveCohortFieldError,
)
from app.infra.profile_identity_context import resolve_profile_identity_context
from app.infra.tools.sanitize import sanitize_model_kwargs
from app.tools.entries.cohort_drafts.create import create_cohort_draft
from app.tools.entries.cohort_drafts.get import get_cohort_drafts
from app.tools.resources.departments.search import search_departments
from app.tools.resources.descriptions.create import create_description
from app.tools.resources.descriptions.search import search_descriptions
from app.tools.resources.flags.search import search_flags
from app.tools.resources.names.create import create_name
from app.tools.resources.names.search import search_names
from app.tools.resources.profiles.search import search_profiles
from app.tools.resources.profile_personas.create import create_profile_persona
from app.tools.resources.simulation_availability.create import (
    create_simulation_availability,
)
from app.tools.resources.simulation_positions.create import (
    create_simulation_position as create_sim_position,
)
from app.tools.resources.simulations.search import search_simulations


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
        # Matchable resources: exact-match lookup only.
        # ------------------------------------------------------------------

        resolved_flag_id = getattr(request, "flag_id", None)
        if resolved_flag_id is None:
            resolved_flag_id = getattr(request, "active_flag_id", None)
        raw_flag = getattr(request, "flag", None)
        if raw_flag is not None and resolved_flag_id is None:
            results = await search_flags(
                conn,
                redis,
                search=raw_flag,
                limit_count=100,
                flag_type="cohort_active",
                cohort=True,
            )
            match = next(
                (
                    flag
                    for flag in results
                    if (
                        isinstance(flag.name, str)
                        and flag.name.lower() == raw_flag.strip().lower()
                    )
                    or (
                        isinstance(flag.type, str)
                        and flag.type.lower() == raw_flag.strip().lower()
                    )
                ),
                None,
            )
            if match and match.id:
                resolved_flag_id = match.id
            else:
                errors.append(
                    SaveCohortFieldError(
                        field="flag",
                        message=f'Flag "{raw_flag}" not found',
                    )
                )

        if (
            getattr(request, "active_flag", None) is not None
            and resolved_flag_id is None
            and bool(getattr(request, "active_flag", None))
        ):
            results = await search_flags(
                conn,
                redis,
                search=None,
                limit_count=1000,
                flag_type="cohort_active",
                cohort=True,
            )
            match = next((flag for flag in results if flag.type == "cohort_active"), None)
            if match and match.id:
                resolved_flag_id = match.id
            else:
                errors.append(
                    SaveCohortFieldError(
                        field="active_flag",
                        message="Active flag resource not found",
                    )
                )
        if resolved_flag_id is not None:
            request.flag_id = resolved_flag_id

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
    # Ack short-circuit.
    # ------------------------------------------------------------------
    if accept is not None and idempotency_key is not None:
        if accept:
            async with pool.acquire() as conn:
                drafts = await get_cohort_drafts(conn, [idempotency_key])
                async with conn.transaction():
                    if drafts:
                        draft = drafts[0]
                        await create_cohort_draft(
                            conn,
                            session_id=session_id,
                            id=idempotency_key,
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
                            session_id=session_id,
                            id=idempotency_key,
                            soft=False,
                            profile_ids=[profile.profiles_id],
                        )
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
            draft_id=idempotency_key,
            idempotency_key=idempotency_key,
            message="Draft accepted" if accept else "Draft rejected",
            form_state=CohortDraftFormState(),
        )

    # Build request from kwargs if not provided directly.
    if request is None:
        filtered = sanitize_model_kwargs(
            kwargs,
            list_fields={
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
            bool_fields={"active_flag"},
            drop_false_bools={"active_flag"},
            value_id_pairs=[
                ("name", "name_id"),
                ("description", "description_id"),
                ("flag", "flag_id"),
                ("active_flag", "active_flag_id"),
            ],
        )
        if idempotency_key is not None and "idempotency_key" not in filtered:
            filtered["idempotency_key"] = idempotency_key
        if accept is not None and "accept" not in filtered:
            filtered["accept"] = accept
        request = PatchCohortDraftApiRequest(**filtered)

    # ------------------------------------------------------------------
    # Step 1: Profile context
    # ------------------------------------------------------------------
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

    # ------------------------------------------------------------------
    # Step 2: Permission check
    # ------------------------------------------------------------------
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
    errors = await _resolve_creatable_values(pool, redis, request)
    if errors:
        raise HTTPException(
            status_code=400,
            detail=[error.model_dump() for error in errors],
        )

    # ------------------------------------------------------------------
    # Step 4: Create draft entry
    # ------------------------------------------------------------------
    resolved_flag_id = getattr(request, "flag_id", None)
    resolved_pending_ids = list(getattr(request, "pending_ids", None) or [])
    async with pool.acquire() as conn:
        async with conn.transaction():
            result = await create_cohort_draft(
                conn,
                session_id=session_id,
                id=idempotency_key,
                soft=soft,
                department_ids=request.department_ids,
                description_ids=[request.description_id]
                if request.description_id
                else None,
                flag_ids=[resolved_flag_id] if resolved_flag_id else None,
                name_ids=[request.name_id] if request.name_id else None,
                profile_persona_ids=request.profile_persona_ids,
                profile_ids=list(dict.fromkeys((request.profile_ids or []) + [profile.profiles_id])),
                simulation_availability_ids=request.simulation_availability_ids,
                simulation_position_ids=request.simulation_position_ids,
                simulation_ids=request.simulation_ids,
                pending_ids=set(resolved_pending_ids) if resolved_pending_ids else None,
            )

    # ------------------------------------------------------------------
    # Step 5: Build form state (server is source of truth)
    # ------------------------------------------------------------------
    form_state = CohortDraftFormState(
        name_id=request.name_id,
        name=getattr(request, "name", None),
        description_id=request.description_id,
        description=getattr(request, "description", None),
        flag_id=resolved_flag_id,
        flag=getattr(request, "flag", None),
        active_flag_id=resolved_flag_id if getattr(request, "active_flag", None) else getattr(request, "active_flag_id", None),
        active_flag=getattr(request, "active_flag", None),
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
    await refresh_cohort_impl(
        pool,
        redis,
        profile_id=profile_id,
        session_id=session_id,
        targets=["cohort_drafts_mv"],
        soft=soft,
        operation_key=idempotency_key or result.id,
    )

    return PatchCohortDraftApiResponse(
        success=True,
        draft_id=result.id,
        idempotency_key=idempotency_key or result.id,
        message="Draft created (pending acceptance)" if soft else "Draft created successfully",
        form_state=form_state,
    )
