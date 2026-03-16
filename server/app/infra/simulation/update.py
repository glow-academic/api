"""Simulation update logic — composable infra architecture.

Composes existing black-box tools:
  1. resolve_profile_identity_context — profile (role, departments)
  2. resolve_simulation_permissions_context — per-item access + edit check
  3. resolve_simulation_values — raw value → ID resolution
  4. update_simulation_artifact — junction writes (partial update)
  5. create_denormalized_snapshot — simulations_resource snapshot
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
from app.tools.artifacts.simulation.update import (
    _UNSET,
)
from app.tools.artifacts.simulation.update import (
    update_simulation as update_simulation_artifact,
)
from app.utils.cache.invalidate_tags import invalidate_tags


async def update_simulation_impl(
    pool: asyncpg.Pool,
    redis: Redis,
    *,
    profile_id: UUID,
    items: list,
    session_id: UUID | None = None,
    draft_id: UUID | None = None,
    group_id: UUID | None = None,
) -> dict:
    """Simulation bulk update using composable infra functions.

    Flow:
      1. resolve_profile_identity_context → role, department_ids
      2. Per-item: resolve_simulation_permissions_context → exists + compute_can_edit
      3. Per-item value resolution (raw → ID, no required field enforcement)
      4. Single transaction: update_simulation_artifact + denormalized snapshot per item
      5. invalidate_tags
    """
    from app.infra.simulation.permissions import compute_can_edit
    from app.infra.simulation.types import (
        SimulationResultItem,
        UpdateSimulationApiResponse,
    )

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

    # ── Step 2: Per-item permission check ──────────────────────────────

    async with pool.acquire() as conn:
        for idx, item in enumerate(items):
            perms = await resolve_simulation_permissions_context(
                conn, item.simulation_id
            )
            if not perms.exists:
                raise HTTPException(
                    status_code=404,
                    detail=f"Item {idx}: Simulation {item.simulation_id} not found.",
                )
            if not compute_can_edit(
                user_role=profile.role,
                simulation_department_ids=perms.department_ids,
                cohort_usage_count=perms.cohort_usage_count,
                user_department_ids=profile.department_ids,
            ):
                raise HTTPException(
                    status_code=403,
                    detail=f"Item {idx}: You don't have permission to update this simulation.",
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
        return UpdateSimulationApiResponse(results=error_results)

    # ── Step 4: Single transaction ─────────────────────────────────────

    results: list[SimulationResultItem] = []

    for item in items:
        # Create denormalized snapshot OUTSIDE transaction (read-only hydration)
        simulations_resource_id = await create_denormalized_snapshot(
            pool,
            redis,
            name_id=item.name_id,
            description_id=item.description_id,
            department_ids=item.department_ids,
            scenario_ids=item.scenario_ids,
            scenario_rubric_ids=item.scenario_rubric_ids,
            scenario_time_limit_ids=item.scenario_time_limit_ids,
            scenario_position_ids=item.scenario_position_ids,
            scenario_flag_ids=item.scenario_flag_ids,
        )

        # Artifact update inside transaction
        async with pool.acquire() as conn:
            async with conn.transaction():
                await update_simulation_artifact(
                    conn,
                    item.simulation_id,
                    name_id=item.name_id if item.name_id else _UNSET,
                    description_id=item.description_id
                    if item.description_id
                    else _UNSET,
                    department_ids=item.department_ids,
                    flag_ids=item.flag_ids,
                    scenario_ids=item.scenario_ids,
                    scenario_flag_ids=item.scenario_flag_ids,
                    scenario_position_ids=item.scenario_position_ids,
                    scenario_rubric_ids=item.scenario_rubric_ids,
                    scenario_time_limit_ids=item.scenario_time_limit_ids,
                    simulation_ids=[simulations_resource_id],
                )

        results.append(
            SimulationResultItem(
                success=True,
                simulation_id=item.simulation_id,
                message="Simulation updated successfully",
            )
        )

    # ── Step 5: Invalidate cache ───────────────────────────────────────

    await invalidate_tags(["simulations"], redis=redis)

    return UpdateSimulationApiResponse(results=results)
