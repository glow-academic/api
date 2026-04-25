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

from app.infra.simulation.refresh import refresh_simulation_impl
from app.infra.profile_identity_context import resolve_profile_identity_context
from app.infra.simulation.permissions_context import (
    create_denormalized_snapshot,
    resolve_simulation_permissions_context,
    resolve_simulation_values,
)
from app.tools.artifacts.simulation.get import get_simulations
from app.tools.artifacts.simulation.update import (
    _UNSET,
)
from app.tools.artifacts.simulation.update import (
    update_simulation as update_simulation_artifact,
)
from app.infra.simulation.types import (
    UpdateSimulationApiRequest,
    UpdateSimulationApiResponse,
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

    Flow:
      1. resolve_profile_identity_context → role, department_ids
      2. Per-item: resolve_simulation_permissions_context → exists + compute_can_edit
      3. Per-item value resolution (raw → ID, no required field enforcement)
      4. Single transaction: update_simulation_artifact + denormalized snapshot per item
      5. canonical refresh via refresh_simulation_impl
    """
    from app.infra.simulation.permissions import compute_can_edit
    from app.infra.simulation.types import (
        SimulationResultItem,
    )

    idempotency_key = idempotency_key or request.idempotency_key
    if idempotency_key and accept is None:
        accept = request.accept

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

    async with pool.acquire() as conn:
        for idx, item in enumerate(items):
            perms = await resolve_simulation_permissions_context(
                conn, item.id
            )
            if not perms.exists:
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
                raise HTTPException(
                    status_code=403,
                    detail=f"Item {idx}: You don't have permission to update this simulation.",
                )

    # ── Step 3: ACK short-circuit ───────────────────────────────────────

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

    # ── Step 4: Per-item value resolution ──────────────────────────────

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

    # ── Step 5: Single transaction ─────────────────────────────────────

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

    return UpdateSimulationApiResponse(results=results, idempotency_key=idempotency_key)
