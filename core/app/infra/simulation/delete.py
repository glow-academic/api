"""Simulation delete logic — composable infra architecture.

Core delete function that composes existing black-box tools:
  1. resolve_profile_identity_context — profile (role)
  2. resolve_simulation_permissions_context — per-item exists, departments, usage
  3. compute_can_delete — permission check
  4. delete_simulations — bulk delete tool
  5. invalidate_tags — cache invalidation
"""

from __future__ import annotations

from uuid import UUID

import asyncpg
from fastapi import HTTPException
from redis.asyncio import Redis

from app.infra.profile_identity_context import resolve_profile_identity_context
from app.infra.simulation.permissions import compute_can_delete
from app.infra.simulation.permissions_context import (
    resolve_simulation_permissions_context,
)
from app.infra.simulation.types import (
    DeleteSimulationApiResponse,
    DeleteSimulationResult,
)
from app.tools.artifacts.simulation.delete import delete_simulations
from app.tools.artifacts.simulation.get import get_simulations
from app.tools.resources.names.get import get_names
from app.utils.cache.invalidate_tags import invalidate_tags


async def delete_simulation_impl(
    pool: asyncpg.Pool,
    redis: Redis,
    *,
    profile_id: UUID,
    simulation_ids: list[UUID],
    session_id: UUID | None = None,
) -> DeleteSimulationApiResponse:
    """Simulation bulk delete using composable infra functions.

    Flow:
      1. resolve_profile_identity_context → role
      2. Per-item: resolve_simulation_permissions_context → exists, departments, usage
      3. Per-item: compute_can_delete → permission check (fail fast)
      4. Fetch names for result messages
      5. Single transaction: delete_simulations → bulk delete
      6. invalidate_tags
    """

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

    # ── Step 2+3: Per-item permission checks (fail fast) ──────────────

    async with pool.acquire() as conn:
        for idx, simulation_id in enumerate(simulation_ids):
            ctx = await resolve_simulation_permissions_context(conn, simulation_id)

            if not ctx.exists:
                raise HTTPException(
                    status_code=404,
                    detail=f"Item {idx}: Simulation {simulation_id} not found.",
                )

            if not compute_can_delete(
                user_role=profile.role,
                simulation_department_ids=ctx.department_ids,
                cohort_usage_count=ctx.cohort_usage_count,
            ):
                raise HTTPException(
                    status_code=403,
                    detail=f"Item {idx}: You don't have permission to delete this simulation.",
                )

    # ── Step 4: Fetch names for result messages ───────────────────────

    name_map: dict[UUID, str] = {}
    async with pool.acquire() as conn:
        artifacts = await get_simulations(conn, simulation_ids, names=True)
        for artifact in artifacts:
            name = "Unknown"
            if artifact.name_ids:
                name_resources = await get_names(conn, artifact.name_ids, redis)
                if name_resources:
                    name = name_resources[0].name or "Unknown"
            name_map[artifact.id] = name

    # ── Step 5: Single transaction — bulk delete ──────────────────────

    async with pool.acquire() as conn:
        async with conn.transaction():
            result = await delete_simulations(conn, simulation_ids)

    # ── Step 6: Invalidate cache ──────────────────────────────────────

    await invalidate_tags(["simulations"], redis=redis)

    results = [
        DeleteSimulationResult(
            success=True,
            simulation_id=pid,
            message=f"Simulation '{name_map.get(pid, 'Unknown')}' deleted successfully",
        )
        for pid in result.deleted_ids
    ]

    return DeleteSimulationApiResponse(results=results)
