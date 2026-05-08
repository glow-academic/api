"""Simulation update logic — composable infra architecture.

Composes existing black-box tools:
  1. resolve_profile_identity_context — profile (role, departments)
  2. resolve_simulation_permissions_context — per-item access + edit check
  3. resolve_simulation_values — raw value → ID resolution
  4. update_simulation_artifact — junction writes (partial update)
  5. create_denormalized_snapshot — simulations_resource snapshot
  6. refresh_simulation_impl — canonical cache refresh
"""

from __future__ import annotations

from uuid import UUID

import asyncpg
from fastapi import HTTPException
from redis.asyncio import Redis

from app.infra.profile_identity_context import resolve_profile_identity_context
from app.infra.simulation.permissions_context import (
    create_denormalized_snapshot,
    resolve_simulation_permissions_context,
    resolve_simulation_values,
)
from app.infra.simulation.refresh import refresh_simulation_impl
from app.infra.simulation.types import (
    UpdateSimulationApiRequest,
    UpdateSimulationApiResponse,
)
from app.tools.artifacts.simulation.get import get_simulations
from app.tools.artifacts.simulation.update import (
    _UNSET,
)
from app.tools.artifacts.simulation.update import (
    update_simulation as update_simulation_artifact,
)
from app.tools.resources.flags.get import get_flags


async def update_simulation_impl(
    pool: asyncpg.Pool,
    redis: Redis,
    *,
    profile_id: UUID,
    request: UpdateSimulationApiRequest,
    session_id: UUID | None = None,
    draft_id: UUID | None = None,
    group_id: UUID | None = None,
    soft: bool = False,
    accept: bool | None = None,
    idempotency_key: UUID | None = None,
) -> UpdateSimulationApiResponse:
    """Simulation bulk update using composable infra functions.

    Three call shapes:
      - First call (explicit): ``request.simulations`` required.
      - First call (all-matching): ``request.all=true`` plus ``patch``
        plus filter fields. The impl resolves matching ids, clones
        the patch per id (stamping each id), then runs the existing
        per-row update flow. Per-row permission failures soft-skip.
      - Ack call: ``idempotency_key`` + ``accept`` only.

    Flow (first call):
      1. (all-matching only) resolve_matching_simulation_ids → synth items
      2. resolve_profile_identity_context → role, department_ids
      3. Per-item: resolve_simulation_permissions_context → exists + compute_can_edit
      4. Per-item value resolution (raw → ID, no required field enforcement)
      5. Single transaction: update_simulation_artifact + denormalized snapshot per item
      6. canonical refresh via refresh_simulation_impl
    """
    from app.infra.simulation.permissions import compute_can_edit
    from app.infra.simulation.types import (
        SimulationResultItem,
    )

    idempotency_key = idempotency_key or request.idempotency_key
    if idempotency_key and accept is None:
        accept = request.accept

    # ── Short-circuit: ack path ───────────────────────────────────────
    if accept is not None and idempotency_key is not None:
        if accept:
            async with pool.acquire() as conn:
                async with conn.transaction():
                    await update_simulation_artifact(
                        conn,
                        idempotency_key,
                        soft=False,
                    )

            async with pool.acquire() as conn:
                artifacts = await get_simulations(
                    conn,
                    [idempotency_key],
                    names=True,
                    descriptions=True,
                    departments=True,
                    flags=True,
                    scenarios=True,
                    scenario_flags=True,
                    scenario_positions=True,
                    scenario_rubrics=True,
                    scenario_time_limits=True,
                )
            if artifacts:
                artifact = artifacts[0]
                practice = False
                if artifact.flag_ids:
                    flag_artifacts = await get_flags(pool,
                        list(artifact.flag_ids),
                        redis,
                        bypass_cache=True,
                    )
                    practice = any(flag.type == "practice" for flag in flag_artifacts)

                await create_denormalized_snapshot(
                    pool,
                    redis,
                    name_id=artifact.name_ids[0] if artifact.name_ids else None,
                    description_id=artifact.description_ids[0]
                    if artifact.description_ids
                    else None,
                    practice=practice,
                    department_ids=artifact.department_ids or None,
                    scenario_ids=artifact.scenario_ids or None,
                    scenario_rubric_ids=artifact.scenario_rubric_ids or None,
                    scenario_time_limit_ids=artifact.scenario_time_limit_ids or None,
                    scenario_position_ids=artifact.scenario_position_ids or None,
                    scenario_flag_ids=artifact.scenario_flag_ids or None,
                )

            await refresh_simulation_impl(
                pool,
                redis,
                profile_id=profile_id,
                session_id=session_id,
                operation_key=idempotency_key,
            )

        return UpdateSimulationApiResponse(
            results=[
                SimulationResultItem(
                    success=True,
                    simulation_id=idempotency_key,
                    message="Update accepted" if accept else "Update rejected",
                )
            ],
            idempotency_key=idempotency_key,
        )

    # ── All-matching path: resolve ids + synthesize per-row items ─────
    # Past the ack short-circuit and ``all=true`` ⇒ enumerate every
    # simulation matching the filter, then clone ``request.patch`` per
    # id (stamping the resolved id). The downstream per-row flow runs
    # unchanged. Per-row permission failures soft-skip (collected into
    # ``skipped_results`` and threaded into the final response).
    skipped_results: list[SimulationResultItem] = []

    if request.all:
        if request.patch is None:
            raise HTTPException(
                status_code=400,
                detail="`patch` is required when `all=true` "
                "(it carries the shared change set applied to every matched row).",
            )
        from app.infra.simulation.resolve_matching_ids import (
            resolve_matching_simulation_ids,
        )
        from app.infra.simulation.types import UpdateSimulationItem

        matching = await resolve_matching_simulation_ids(
            pool, redis,
            profile_id=profile_id,
            search=request.search,
            filter_scenario_ids=request.filter_scenario_ids,
            filter_cohort_ids=request.filter_cohort_ids,
            filter_department_ids=request.filter_department_ids,
            scenario_search=request.scenario_search,
            cohort_search=request.cohort_search,
            department_search=request.department_search,
            flag_search=request.flag_search,
        )
        excluded = set(request.excluded_ids or [])
        resolved_ids = [sid for sid in matching if sid not in excluded]

        if not resolved_ids:
            # Empty matching set — well-formed intent, just no rows.
            return UpdateSimulationApiResponse(
                results=[], idempotency_key=idempotency_key,
            )

        # Clone the patch per matched row, stamping the resolved id.
        # ``model_dump(exclude_unset=True, exclude={"id"})`` keeps sparse
        # semantics — only fields the client actually set are written.
        patch_fields = request.patch.model_dump(exclude_unset=True, exclude={"id"})
        synth_items = [UpdateSimulationItem(id=sid, **patch_fields) for sid in resolved_ids]
        # Splice into the request shape downstream code expects.
        request = request.model_copy(update={"simulations": synth_items})

    # ── First-call requirements ───────────────────────────────────────
    if not request.simulations:
        raise HTTPException(
            status_code=400,
            detail="`request.simulations` is required for first-call update "
            "(or pass `idempotency_key` + `accept` for the ack call, "
            "or `all=true` with `patch` and filter fields).",
        )

    items = request.simulations

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

    # ── Step 2: Per-item permission check ──────────────────────────────
    # Explicit path fails fast (existing behavior).
    # All-matching path soft-skips so the response carries per-row
    # outcomes without aborting rows the user CAN edit.
    is_all_matching = bool(request.all)
    permitted_items: list = []

    async with pool.acquire() as conn:
        for idx, item in enumerate(items):
            perms = await resolve_simulation_permissions_context(
                conn, item.id
            )
            if not perms.exists:
                if is_all_matching:
                    skipped_results.append(SimulationResultItem(
                        success=False, simulation_id=item.id,
                        message=f"Simulation {item.id} not found (skipped)",
                    ))
                    continue
                raise HTTPException(
                    status_code=404,
                    detail=f"Item {idx}: Simulation {item.id} not found.",
                )
            if not compute_can_edit(
                role_level=profile.role_level, role_permissions=profile.role_permissions,
                simulation_department_ids=perms.department_ids,
                cohort_usage_count=perms.cohort_usage_count,
                user_department_ids=profile.department_ids,
            ):
                if is_all_matching:
                    skipped_results.append(SimulationResultItem(
                        success=False, simulation_id=item.id,
                        message=f"No permission to update simulation {item.id} (skipped)",
                    ))
                    continue
                raise HTTPException(
                    status_code=403,
                    detail=f"Item {idx}: You don't have permission to update this simulation.",
                )

            permitted_items.append(item)

    if is_all_matching:
        items = permitted_items
        if not items:
            return UpdateSimulationApiResponse(
                results=skipped_results,
                idempotency_key=idempotency_key,
            )

    # ── Step 3: Per-item value resolution ──────────────────────────────

    has_errors = False
    error_results: list[SimulationResultItem] = []

    for idx, item in enumerate(items):
        item_errors = await resolve_simulation_values(
            pool, redis, item, is_create=False
        )
        if item_errors:
            has_errors = True
            error_results.append(
                SimulationResultItem(
                    success=False,
                    message=f"Item {idx}: Validation errors",
                    errors=item_errors,
                )
            )
        else:
            error_results.append(
                SimulationResultItem(success=True, message="Validated")
            )

    if has_errors:
        return UpdateSimulationApiResponse(
            results=error_results,
            idempotency_key=idempotency_key,
        )

    # ── Step 4: Single transaction ─────────────────────────────────────

    results: list[SimulationResultItem] = []

    for item in items:
        # Create denormalized snapshot outside the transaction unless soft=True.
        simulations_resource_id = None
        if not soft:
            practice = False
            if item.flag_ids:
                async with pool.acquire() as conn:
                    flag_artifacts = await get_flags(
                        conn,
                        list(item.flag_ids),
                        redis,
                        bypass_cache=True,
                    )
                practice = any(flag.type == "practice" and flag.value is True for flag in flag_artifacts)
            simulations_resource_id = await create_denormalized_snapshot(
                pool,
                redis,
                name_id=item.name_id,
                description_id=item.description_id,
                practice=practice,
                department_ids=item.department_ids,
                scenario_ids=item.scenario_ids,
                scenario_rubric_ids=item.scenario_rubric_ids,
                scenario_time_limit_ids=item.scenario_time_limit_ids,
                scenario_position_ids=item.scenario_position_ids,
                scenario_flag_ids=item.scenario_flag_ids,
            )

        combined_flag_ids: list[UUID] = list(item.flag_ids or [])

        # Artifact update inside transaction
        async with pool.acquire() as conn:
            async with conn.transaction():
                await update_simulation_artifact(
                    conn,
                    item.id,
                    name_id=item.name_id if item.name_id else _UNSET,
                    description_id=item.description_id
                    if item.description_id
                    else _UNSET,
                    department_ids=item.department_ids,
                    flag_ids=combined_flag_ids or None,
                    scenario_ids=item.scenario_ids,
                    scenario_flag_ids=item.scenario_flag_ids,
                    scenario_position_ids=item.scenario_position_ids,
                    scenario_rubric_ids=item.scenario_rubric_ids,
                    scenario_time_limit_ids=item.scenario_time_limit_ids,
                    simulation_ids=[simulations_resource_id]
                    if simulations_resource_id
                    else None,
                    soft=soft,
                )

        results.append(
            SimulationResultItem(
                success=True,
                simulation_id=item.id,
                message="Simulation updated (pending acceptance)"
                if soft
                else "Simulation updated successfully",
            )
        )

    # ── Step 6: Canonical refresh ──────────────────────────────────────

    await refresh_simulation_impl(
        pool,
        redis,
        profile_id=profile_id,
        session_id=session_id,
        soft=soft,
        operation_key=idempotency_key or (results[0].simulation_id if results else None),
    )

    # All-matching path threads soft-skipped rows back into the response
    # so the client can surface "X updated, Y skipped" in one toast.
    # Explicit path's ``skipped_results`` is empty.
    return UpdateSimulationApiResponse(
        results=results + skipped_results,
        idempotency_key=idempotency_key,
    )
