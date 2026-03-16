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
from pydantic import BaseModel, Field
from redis.asyncio import Redis

from app.infra.profile_identity_context import resolve_profile_identity_context
from app.infra.simulation.permissions_context import (
    create_denormalized_snapshot,
    resolve_simulation_values,
)
from app.tools.artifacts.simulation.create import (
    create_simulation as create_simulation_artifact,
)
from app.utils.cache.invalidate_tags import invalidate_tags


class CreateSimulationItem(BaseModel):
    """Single simulation item for create — no simulation_id.

    Required fields (name): provide ID or value.
    """

    id: UUID | None = Field(None, description="Client-provided UUID for the simulation")

    # Required single-select — provide ID or value
    name_id: UUID | None = Field(None, description="UUID of the name resource")
    name: str | None = Field(None, description="Display name value")
    # Optional single-select — provide ID or value
    description_id: UUID | None = Field(None, description="UUID of the description resource")
    description: str | None = Field(None, description="Description text value")
    # Multi-select IDs
    flag_ids: list[UUID] | None = Field(None, description="Associated flag UUIDs")
    department_ids: list[UUID] | None = Field(None, description="Associated department UUIDs")
    scenario_ids: list[UUID] | None = Field(None, description="Associated scenario UUIDs")
    scenario_flag_ids: list[UUID] | None = Field(None, description="Associated scenario flag UUIDs")
    scenario_position_ids: list[UUID] | None = Field(None, description="Associated scenario position UUIDs")
    scenario_rubric_ids: list[UUID] | None = Field(None, description="Associated scenario rubric UUIDs")
    scenario_time_limit_ids: list[UUID] | None = Field(None, description="Associated scenario time limit UUIDs")
    # Value-based fields for CSV import (match-by-name resolution)
    is_inactive: bool | None = Field(None, description="Whether the simulation is inactive")
    is_practice: bool | None = Field(None, description="Whether this is a practice simulation")
    departments: list[str] | None = Field(None, description="Department names for matching")
    scenarios: list[str] | None = Field(None, description="Scenario names for matching")


class SimulationFieldError(BaseModel):
    """Per-field error from value resolution."""

    field: str = Field(..., description="Name of the field with the error")
    message: str = Field(..., description="Human-readable error message")


class SimulationResultItem(BaseModel):
    """Per-item result within a bulk create/update response."""

    success: bool = Field(..., description="Whether the operation succeeded")
    simulation_id: UUID | None = Field(None, description="UUID of the affected simulation")
    message: str = Field(..., description="Human-readable result message")
    errors: list[SimulationFieldError] | None = Field(None, description="List of per-field errors")


class CreateSimulationApiResponse(BaseModel):
    """Response model for bulk create simulation endpoint."""

    results: list[SimulationResultItem] = Field(..., description="List of operation results")


async def create_simulation_impl(
    pool: asyncpg.Pool,
    redis: Redis,
    *,
    profile_id: UUID,
    items: list,
    session_id: UUID | None = None,
    draft_id: UUID | None = None,
    group_id: UUID | None = None,
) -> dict:
    """Simulation bulk create using composable infra functions.

    Flow:
      1. resolve_profile_identity_context → role, department_ids
      2. compute_can_create — single check (applies to all items)
      3. Per-item value resolution (raw → ID, required field enforcement)
      4. Single transaction: create_simulation_artifact + denormalized snapshot per item
      5. invalidate_tags
    """
    from app.infra.simulation.permissions import compute_can_create

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
        user_role=profile.role,
        department_ids=requested_department_ids or None,
    ):
        raise HTTPException(
            status_code=403,
            detail="You don't have permission to create simulations.",
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
        return CreateSimulationApiResponse(results=error_results)

    # ── Step 4: Single transaction ─────────────────────────────────────

    results: list[SimulationResultItem] = []

    for item in items:
        # Create denormalized snapshot OUTSIDE transaction (read-only hydration)
        simulations_resource_id = await create_denormalized_snapshot(
            pool,
            redis,
            id=item.id,
            name_id=item.name_id,
            description_id=item.description_id,
            department_ids=item.department_ids,
            scenario_ids=item.scenario_ids,
            scenario_rubric_ids=item.scenario_rubric_ids,
            scenario_time_limit_ids=item.scenario_time_limit_ids,
            scenario_position_ids=item.scenario_position_ids,
            scenario_flag_ids=item.scenario_flag_ids,
        )

        # Artifact create inside transaction
        async with pool.acquire() as conn:
            async with conn.transaction():
                result = await create_simulation_artifact(
                    conn,
                    id=item.id,
                    name_id=item.name_id,
                    description_id=item.description_id,
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
                simulation_id=result.id,
                message="Simulation created successfully",
            )
        )

    # ── Step 5: Invalidate cache ───────────────────────────────────────

    await invalidate_tags(["simulations"], redis=redis)

    return CreateSimulationApiResponse(results=results)
