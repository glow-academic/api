"""Rubric create logic — composable infra architecture.

Composes existing black-box tools:
  1. resolve_profile_identity_context — profile (role, departments)
  2. compute_can_create — permission check
  3. resolve_rubric_values — raw value → ID resolution
  4. create_rubric_artifact — junction writes
  5. create_denormalized_snapshot — rubrics_resource snapshot
"""

from __future__ import annotations

from uuid import UUID

import asyncpg
from fastapi import HTTPException
from pydantic import BaseModel, Field
from redis.asyncio import Redis

from app.infra.profile_identity_context import resolve_profile_identity_context
from app.infra.rubric.permissions_context import (
    create_denormalized_snapshot,
    resolve_rubric_values,
)
from app.tools.artifacts.rubric.create import (
    create_rubric as create_rubric_artifact,
)
from app.utils.cache.invalidate_tags import invalidate_tags


class CreateRubricItem(BaseModel):
    """Single rubric item for create — no rubric_id."""

    id: UUID | None = Field(None, description="Optional pre-assigned UUID")

    # Required single-select — provide ID or value
    name_id: UUID | None = Field(None, description="Name resource UUID")
    name: str | None = Field(None, description="Name value for resolution")
    # Optional single-select — provide ID or value
    description_id: UUID | None = Field(None, description="Description resource UUID")
    description: str | None = Field(None, description="Description value for resolution")
    active_flag_id: UUID | None = Field(None, description="Active flag option UUID")
    active_flag: bool | None = Field(None, description="Active flag boolean value")
    # Optional multi-select — provide IDs or values
    department_ids: list[UUID] | None = Field(None, description="Department UUIDs")
    departments: list[str] | None = Field(None, description="Department names for resolution")
    # ID-only fields
    point_ids: list[UUID] | None = Field(None, description="Point UUIDs")
    standard_group_ids: list[UUID] | None = Field(None, description="Standard group UUIDs")
    standard_ids: list[UUID] | None = Field(None, description="Standard UUIDs")


class RubricFieldError(BaseModel):
    """Per-field error from value resolution."""

    field: str = Field(..., description="Field name that has the error")
    message: str = Field(..., description="Human-readable error message")


class RubricResultItem(BaseModel):
    """Per-item result within a bulk create/update response."""

    success: bool = Field(..., description="Whether the operation succeeded")
    rubric_id: UUID | None = Field(None, description="Rubric UUID")
    message: str = Field(..., description="Human-readable result message")
    errors: list[RubricFieldError] | None = Field(None, description="List of per-field errors")


class CreateRubricApiResponse(BaseModel):
    """Response model for bulk create rubric endpoint."""

    results: list[RubricResultItem] = Field(..., description="List of operation results")


async def create_rubric_impl(
    pool: asyncpg.Pool,
    redis: Redis,
    *,
    profile_id: UUID,
    items: list,
    session_id: UUID | None = None,
    draft_id: UUID | None = None,
    group_id: UUID | None = None,
) -> dict:
    """Rubric bulk create using composable infra functions.

    Flow:
      1. resolve_profile_identity_context → role, department_ids
      2. compute_can_create — single check (applies to all items)
      3. Per-item value resolution (raw → ID, required field enforcement)
      4. Single transaction: create_rubric_artifact + denormalized snapshot per item
      5. invalidate_tags
    """
    from app.infra.rubric.permissions import compute_can_create

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

    if not compute_can_create(user_role=profile.role, department_ids=None):
        raise HTTPException(
            status_code=403,
            detail="You don't have permission to create rubrics.",
        )

    # ── Step 3: Per-item value resolution ──────────────────────────────

    has_errors = False
    error_results: list[RubricResultItem] = []

    async with pool.acquire() as conn:
        for idx, item in enumerate(items):
            item_errors = await resolve_rubric_values(conn, redis, item, is_create=True)
            if item_errors:
                has_errors = True
                error_results.append(
                    RubricResultItem(
                        success=False,
                        message=f"Item {idx}: Validation errors",
                        errors=item_errors,
                    )
                )
            else:
                error_results.append(
                    RubricResultItem(success=True, message="Validated")
                )

    if has_errors:
        return CreateRubricApiResponse(results=error_results)

    # ── Step 4: Single transaction ─────────────────────────────────────

    results: list[RubricResultItem] = []

    for item in items:
        # Create denormalized snapshot OUTSIDE transaction (read-only hydration)
        rubrics_resource_id = await create_denormalized_snapshot(
            pool,
            redis,
            id=item.id,
            name_id=item.name_id,
            description_id=item.description_id,
            department_ids=item.department_ids,
            standard_group_ids=item.standard_group_ids,
        )

        # Artifact create inside transaction
        async with pool.acquire() as conn:
            async with conn.transaction():
                result = await create_rubric_artifact(
                    conn,
                    id=item.id,
                    name_id=item.name_id,
                    description_id=item.description_id,
                    department_ids=item.department_ids,
                    flag_ids=[item.active_flag_id] if item.active_flag_id else None,
                    point_ids=item.point_ids,
                    standard_group_ids=item.standard_group_ids,
                    standard_ids=item.standard_ids,
                    rubric_ids=[rubrics_resource_id],
                )

        results.append(
            RubricResultItem(
                success=True,
                rubric_id=result.id,
                message="Rubric created successfully",
            )
        )

    # ── Step 5: Invalidate cache ───────────────────────────────────────

    await invalidate_tags(["rubrics"], redis=redis)

    return CreateRubricApiResponse(results=results)
