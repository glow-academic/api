"""Simulation create logic — composable infra architecture.

Composes existing black-box tools:
  1. resolve_profile_identity_context — profile (role, departments)
  2. compute_can_create — permission check
  3. resolve_simulation_values — raw value → ID resolution
  4. create_simulation_artifact — junction writes
  5. create_denormalized_snapshot — simulations_resource snapshot
"""

from __future__ import annotations

from uuid import UUID

import asyncpg
from fastapi import HTTPException
from redis.asyncio import Redis

from app.infra.profile_identity_context import resolve_profile_identity_context
from app.infra.simulation.refresh import refresh_simulation_impl
from app.infra.simulation.permissions_context import (
    create_denormalized_snapshot,
    resolve_simulation_values,
)
from app.tools.artifacts.simulation.create import (
    create_simulation as create_simulation_artifact,
)
from app.tools.artifacts.simulation.get import get_simulations


from app.infra.simulation.types import (
    CreateSimulationApiRequest,
    CreateSimulationApiResponse,
    SimulationResultItem,
)


async def create_simulation_impl(
    pool: asyncpg.Pool,
    redis: Redis,
    *,
    profile_id: UUID,
    request: CreateSimulationApiRequest,
    session_id: UUID | None = None,
    draft_id: UUID | None = None,
    group_id: UUID | None = None,
    soft: bool = False,
    accept: bool | None = None,
    idempotency_key: UUID | None = None,
) -> CreateSimulationApiResponse:
    """Simulation bulk create using composable infra functions.

    Flow:
      1. resolve_profile_identity_context → role, department_ids
      2. compute_can_create — single check (applies to all items)
      3. ACK short-circuit for dormant create promotion/rejection
      4. Per-item value resolution (raw → ID, required field enforcement)
      5. Single transaction: create_simulation_artifact + denormalized snapshot per item
      6. Refresh via canonical simulation refresh
    """
    from app.infra.simulation.permissions import compute_can_create

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
        draft_id=draft_id,
    )

    if profile is None:
        raise HTTPException(
            status_code=401,
            detail="Profile not found. Please sign in again.",
        )

    # ── Step 2: Permission check ───────────────────────────────────────

    requested_department_ids = [
        department_id for item in items for department_id in (item.department_ids or [])
    ]

    if not compute_can_create(
        role_level=profile.role_level, role_permissions=profile.role_permissions,
        department_ids=requested_department_ids or None,
    ):
        raise HTTPException(
            status_code=403,
            detail="You don't have permission to create simulations.",
        )

    # ── Short-circuit: ack path ───────────────────────────────────────

    if accept is not None and idempotency_key is not None:
        if accept:
            async with pool.acquire() as conn:
                async with conn.transaction():
                    await create_simulation_artifact(
                        conn,
                        id=idempotency_key,
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
                    simulations=True,
                )
            if artifacts:
                artifact = artifacts[0]
                practice = False
                if artifact.flag_ids:
                    async with pool.acquire() as conn:
                        flag_artifacts = await get_flags(
                            conn,
                            list(artifact.flag_ids),
                            redis,
                            bypass_cache=True,
                        )
                    practice = any(flag.type == "practice" for flag in flag_artifacts)
                await create_denormalized_snapshot(
                    pool,
                    redis,
                    id=artifact.id,
                    name_id=artifact.name_ids[0] if artifact.name_ids else None,
                    description_id=artifact.description_ids[0] if artifact.description_ids else None,
                    practice=practice,
                    department_ids=artifact.department_ids,
                    scenario_ids=artifact.scenario_ids,
                    scenario_rubric_ids=artifact.scenario_rubric_ids,
                    scenario_time_limit_ids=artifact.scenario_time_limit_ids,
                    scenario_position_ids=artifact.scenario_position_ids,
                    scenario_flag_ids=artifact.scenario_flag_ids,
                )

            await refresh_simulation_impl(
                pool,
                redis,
                profile_id=profile_id,
                session_id=session_id,
                operation_key=idempotency_key,
            )

        return CreateSimulationApiResponse(
            results=[
                SimulationResultItem(
                    success=True,
                    simulation_id=idempotency_key,
                    message="Simulation accepted" if accept else "Simulation rejected",
                )
            ],
            idempotency_key=idempotency_key,
        )

    # ── Step 3: Per-item value resolution ──────────────────────────────

    has_errors = False
    error_results: list[SimulationResultItem] = []

    for idx, item in enumerate(items):
        item_errors = await resolve_simulation_values(pool, redis, item, is_create=True)
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
        return CreateSimulationApiResponse(
            results=error_results,
            idempotency_key=idempotency_key,
        )

    # ── Step 4: Denormalized snapshots (skip when soft — dormant artifact) ─

    results: list[SimulationResultItem] = []

    snapshot_ids: list[UUID] = []
    if not soft:
        for item in items:
            simulations_resource_id = await create_denormalized_snapshot(
                pool,
                redis,
                id=item.resource_id,
                name_id=item.name_id,
                description_id=item.description_id,
                practice=bool(item.practice_flag_id),
                department_ids=item.department_ids,
                scenario_ids=item.scenario_ids,
                scenario_rubric_ids=item.scenario_rubric_ids,
                scenario_time_limit_ids=item.scenario_time_limit_ids,
                scenario_position_ids=item.scenario_position_ids,
                scenario_flag_ids=item.scenario_flag_ids,
            )
            snapshot_ids.append(simulations_resource_id)

    # ── Step 5: Single transaction — artifact writes ───────────────────

    async with pool.acquire() as conn:
        async with conn.transaction():
            for idx, item in enumerate(items):
                combined_flag_ids: list[UUID] = []
                if item.active_flag_id:
                    combined_flag_ids.append(item.active_flag_id)
                if item.practice_flag_id:
                    combined_flag_ids.append(item.practice_flag_id)

                result = await create_simulation_artifact(
                    conn,
                    id=item.id,
                    name_id=item.name_id,
                    description_id=item.description_id,
                    department_ids=item.department_ids,
                    flag_ids=combined_flag_ids or None,
                    scenario_ids=item.scenario_ids,
                    scenario_flag_ids=item.scenario_flag_ids,
                    scenario_position_ids=item.scenario_position_ids,
                    scenario_rubric_ids=item.scenario_rubric_ids,
                    scenario_time_limit_ids=item.scenario_time_limit_ids,
                    simulation_ids=[snapshot_ids[idx]] if snapshot_ids else None,
                    soft=soft,
                )

                results.append(
                    SimulationResultItem(
                        success=True,
                        simulation_id=result.id,
                        message="Simulation created (pending acceptance)" if soft else "Simulation created successfully",
                    )
                )

    # ── Step 6: Refresh via canonical simulation refresh ───────────────

    await refresh_simulation_impl(
        pool,
        redis,
        profile_id=profile_id,
        session_id=session_id,
        soft=soft,
        operation_key=idempotency_key or (results[0].simulation_id if results else None),
    )

    return CreateSimulationApiResponse(results=results, idempotency_key=idempotency_key)
