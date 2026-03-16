"""Scenario create logic — composable infra architecture.

Composes existing black-box tools:
  1. resolve_profile_identity_context — profile (role, departments)
  2. compute_can_create — permission check
  3. resolve_scenario_values — raw value → ID resolution
  4. create_scenario_artifact — junction writes
  5. create_denormalized_snapshot — scenarios_resource snapshot
"""

from __future__ import annotations

from uuid import UUID

import asyncpg
from fastapi import HTTPException
from pydantic import BaseModel, Field
from redis.asyncio import Redis

from app.infra.profile_identity_context import resolve_profile_identity_context
from app.infra.scenario.permissions_context import (
    create_denormalized_snapshot,
    resolve_scenario_values,
)
from app.tools.artifacts.scenario.create import (
    create_scenario as create_scenario_artifact,
)
from app.utils.cache.invalidate_tags import invalidate_tags


class CreateScenarioItem(BaseModel):
    """Single scenario item for create — no scenario_id.

    Required fields (name): provide ID or value.
    """

    id: UUID | None = Field(None, description="Client-provided UUID for the scenario")

    # Dual-mode: provide ID or raw value
    name_id: UUID | None = Field(None, description="UUID of the name resource")
    name: str | None = Field(None, description="Display name value")
    description_id: UUID | None = Field(None, description="UUID of the description resource")
    description: str | None = Field(None, description="Description text value")
    problem_statement_id: UUID | None = Field(None, description="UUID of the problem statement resource")
    problem_statement: str | None = Field(None, description="Problem statement text value")
    # Flag IDs (individual typed flags)
    active_flag_id: UUID | None = Field(None, description="UUID of the active flag option")
    objectives_enabled_flag_id: UUID | None = Field(None, description="UUID of the objectives enabled flag option")
    images_enabled_flag_id: UUID | None = Field(None, description="UUID of the images enabled flag option")
    video_enabled_flag_id: UUID | None = Field(None, description="UUID of the video enabled flag option")
    questions_enabled_flag_id: UUID | None = Field(None, description="UUID of the questions enabled flag option")
    problem_statement_enabled_flag_id: UUID | None = Field(None, description="UUID of the problem statement enabled flag option")
    # Multi-select resource IDs
    department_ids: list[UUID] | None = Field(None, description="Associated department UUIDs")
    persona_ids: list[UUID] | None = Field(None, description="Associated persona UUIDs")
    document_ids: list[UUID] | None = Field(None, description="Associated document UUIDs")
    parameter_ids: list[UUID] | None = Field(None, description="Associated parameter UUIDs")
    parameter_field_ids: list[UUID] | None = Field(None, description="Associated parameter field UUIDs")
    image_ids: list[UUID] | None = Field(None, description="Associated image UUIDs")
    objective_ids: list[UUID] | None = Field(None, description="Associated objective UUIDs")
    video_ids: list[UUID] | None = Field(None, description="Associated video UUIDs")
    question_ids: list[UUID] | None = Field(None, description="Associated question UUIDs")
    option_ids: list[UUID] | None = Field(None, description="Associated option UUIDs")
    # Value-based fields for CSV import (resolved to IDs server-side)
    active_flag: bool | None = Field(None, description="Active flag boolean value")
    departments: list[str] | None = Field(None, description="Department names for matching")
    personas: list[str] | None = Field(None, description="Persona names for matching")
    documents: list[str] | None = Field(None, description="Document names for matching")
    parameter_fields: list[str] | None = Field(None, description="Parameter field names for matching")
    objectives: list[str] | None = Field(None, description="Objective texts for matching")
    images: list[str] | None = Field(None, description="Image names for matching")
    videos: list[str] | None = Field(None, description="Video names for matching")
    questions: list[str] | None = Field(None, description="Question texts for matching")
    options: list[str] | None = Field(None, description="Option texts for matching")


class ScenarioFieldError(BaseModel):
    """Per-field error from value resolution."""

    field: str = Field(..., description="Name of the field with the error")
    message: str = Field(..., description="Human-readable error message")


class ScenarioResultItem(BaseModel):
    """Per-item result within a bulk create/update response."""

    success: bool = Field(..., description="Whether the operation succeeded")
    scenario_id: UUID | None = Field(None, description="UUID of the affected scenario")
    message: str = Field(..., description="Human-readable result message")
    errors: list[ScenarioFieldError] | None = Field(None, description="List of per-field errors")


class CreateScenarioApiResponse(BaseModel):
    """Response model for bulk create scenario endpoint."""

    results: list[ScenarioResultItem] = Field(..., description="List of operation results")


def _batch_department_scope(items: list[CreateScenarioItem]) -> list[str] | None:
    """Summarize whether every item is department-scoped for create permissions."""
    if not items:
        return None

    for item in items:
        if not (item.department_ids or item.departments):
            return None

    return ["department-scoped"]


def _collect_flag_ids(item: CreateScenarioItem) -> list[UUID] | None:
    """Collect all non-None flag IDs from the item into a single list."""
    flag_ids = []
    for fid in [
        item.active_flag_id,
        item.objectives_enabled_flag_id,
        item.images_enabled_flag_id,
        item.video_enabled_flag_id,
        item.questions_enabled_flag_id,
        item.problem_statement_enabled_flag_id,
    ]:
        if fid is not None:
            flag_ids.append(fid)
    return flag_ids if flag_ids else None


async def create_scenario_impl(
    pool: asyncpg.Pool,
    redis: Redis,
    *,
    profile_id: UUID,
    items: list,
    session_id: UUID | None = None,
    draft_id: UUID | None = None,
    group_id: UUID | None = None,
) -> dict:
    """Scenario bulk create using composable infra functions.

    Flow:
      1. resolve_profile_identity_context → role, department_ids
      2. compute_can_create — single check (applies to all items)
      3. Per-item value resolution (raw → ID, required field enforcement)
      4. Single transaction: create_scenario_artifact + denormalized snapshot per item
      5. invalidate_tags
    """
    from app.infra.scenario.permissions import compute_can_create

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

    if not compute_can_create(
        user_role=profile.role,
        department_ids=_batch_department_scope(items),
    ):
        raise HTTPException(
            status_code=403,
            detail="You don't have permission to create scenarios.",
        )

    # ── Step 3: Per-item value resolution ──────────────────────────────

    has_errors = False
    error_results: list[ScenarioResultItem] = []

    for idx, item in enumerate(items):
        item_errors = await resolve_scenario_values(pool, redis, item, is_create=True)
        if item_errors:
            has_errors = True
            error_results.append(
                ScenarioResultItem(
                    success=False,
                    message=f"Item {idx}: Validation errors",
                    errors=item_errors,
                )
            )
        else:
            error_results.append(ScenarioResultItem(success=True, message="Validated"))

    if has_errors:
        return CreateScenarioApiResponse(results=error_results)

    # ── Step 4: Single transaction ─────────────────────────────────────

    results: list[ScenarioResultItem] = []

    for item in items:
        # Create denormalized snapshot OUTSIDE transaction (read-only hydration)
        scenarios_resource_id = await create_denormalized_snapshot(
            pool,
            redis,
            id=item.id,
            name_id=item.name_id,
            description_id=item.description_id,
            department_ids=item.department_ids,
            persona_ids=item.persona_ids,
            parameter_field_ids=item.parameter_field_ids,
            document_ids=item.document_ids,
            objective_ids=item.objective_ids,
            image_ids=item.image_ids,
            video_ids=item.video_ids,
            question_ids=item.question_ids,
            option_ids=item.option_ids,
            problem_statement_ids=[item.problem_statement_id]
            if item.problem_statement_id
            else None,
        )

        flag_ids = _collect_flag_ids(item)

        # Artifact create inside transaction
        async with pool.acquire() as conn:
            async with conn.transaction():
                result = await create_scenario_artifact(
                    conn,
                    id=item.id,
                    name_id=item.name_id,
                    description_id=item.description_id,
                    department_ids=item.department_ids,
                    flag_ids=flag_ids,
                    document_ids=item.document_ids,
                    image_ids=item.image_ids,
                    objective_ids=item.objective_ids,
                    option_ids=item.option_ids,
                    parameter_field_ids=item.parameter_field_ids,
                    persona_ids=item.persona_ids,
                    problem_statement_ids=[item.problem_statement_id]
                    if item.problem_statement_id
                    else None,
                    question_ids=item.question_ids,
                    video_ids=item.video_ids,
                    scenario_ids=[scenarios_resource_id],
                )

        results.append(
            ScenarioResultItem(
                success=True,
                scenario_id=result.id,
                message="Scenario created successfully",
            )
        )

    # ── Step 5: Invalidate cache ───────────────────────────────────────

    await invalidate_tags(["scenarios"], redis=redis)

    return CreateScenarioApiResponse(results=results)
