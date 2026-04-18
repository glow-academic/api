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
from app.infra.tools.sanitize import sanitize_model_kwargs
from app.infra.simulation.permissions import compute_can_draft
from app.infra.simulation.refresh import refresh_simulation_impl
from app.infra.simulation.types import (
    PatchSimulationDraftApiRequest,
    PatchSimulationDraftApiResponse,
    SaveSimulationFieldError,
    SimulationDraftFormState,
)
from app.tools.entries.simulation_drafts.create import (
    create_simulation_draft,
)
from app.tools.resources.descriptions.create import create_description
from app.tools.resources.descriptions.search import search_descriptions
from app.tools.resources.names.create import create_name
from app.tools.resources.names.search import search_names
from app.tools.resources.scenario_flags.create import create_scenario_flag
from app.tools.resources.scenario_positions.create import (
    create_scenario_position,
)
from app.tools.resources.scenario_rubrics.create import create_scenario_rubric
from app.tools.resources.scenario_time_limits.create import (
    create_scenario_time_limit,
)

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
        if accept:
            async with pool.acquire() as conn:
                drafts = await get_simulation_drafts(conn, [idempotency_key])
                async with conn.transaction():
                    if drafts:
                        draft = drafts[0]
                        await create_simulation_draft(
                            conn,
                            session_id=session_id,
                            id=idempotency_key,
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
                            session_id=session_id,
                            id=idempotency_key,
                            soft=False,
                            profile_ids=[profile.profiles_id],
                        )
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
            draft_id=idempotency_key,
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

    errors = await _resolve_creatable_values(pool, redis, request)
    if errors:
        raise HTTPException(
            status_code=400,
            detail=[e.model_dump() for e in errors],
        )

    # ── Step 4: Create draft entry (append-only snapshot) ──────────────

    async with pool.acquire() as conn:
        async with conn.transaction():
            result = await create_simulation_draft(
                conn,
                session_id=session_id,
                id=idempotency_key,
                soft=soft,
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

    # ── Step 5: Canonical refresh ──────────────────────────────────────

    await refresh_simulation_impl(
        pool,
        redis,
        profile_id=profile_id,
        session_id=session_id,
        targets=["simulation_drafts_mv"],
        soft=soft,
        operation_key=idempotency_key or result.id,
    )

    # ── Step 6: Build form state (server is source of truth) ──────────

    form_state = SimulationDraftFormState(
        name_id=request.name_id,
        name=request.name,
        description_id=request.description_id,
        description=request.description,
        flag_ids=request.flag_ids or [],
        department_ids=request.department_ids or [],
        scenario_ids=request.scenario_ids or [],
        scenario_flag_ids=request.scenario_flag_ids or [],
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
