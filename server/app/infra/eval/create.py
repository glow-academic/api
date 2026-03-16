"""Eval create logic — composable infra architecture.

Composes existing black-box tools:
  1. resolve_profile_identity_context — profile (role, departments)
  2. compute_can_create — permission check
  3. resolve_eval_values — raw value → ID resolution
  4. create_eval_artifact — junction writes
  5. create_denormalized_snapshot — evals_resource snapshot
"""

from __future__ import annotations

from uuid import UUID

import asyncpg
from fastapi import HTTPException
from pydantic import BaseModel, Field
from redis.asyncio import Redis

from app.infra.eval.permissions_context import (
    create_denormalized_snapshot,
    resolve_eval_values,
)
from app.infra.profile_identity_context import resolve_profile_identity_context
from app.tools.artifacts.eval.create import (
    create_eval as create_eval_artifact,
)
from app.utils.cache.invalidate_tags import invalidate_tags


class CreateEvalItem(BaseModel):
    """Single eval item for create — no eval_id.

    Required fields (name): provide ID or value.
    """

    id: UUID | None = Field(None, description="Optional pre-assigned UUID")

    # Required single-select — provide ID or value
    name_id: UUID | None = Field(None, description="Name resource UUID")
    name: str | None = Field(None, description="Name value for resolution")
    # Optional single-select — provide ID or value
    description_id: UUID | None = Field(None, description="Description resource UUID")
    description: str | None = Field(None, description="Description value for resolution")
    # Multi-select — IDs only (matching get.py junctions)
    flag_ids: list[UUID] | None = Field(None, description="Flag option UUIDs")
    department_ids: list[UUID] | None = Field(None, description="Department UUIDs")
    departments: list[str] | None = Field(None, description="Department names for resolution")
    model_ids: list[UUID] | None = Field(None, description="Model UUIDs")
    model_flag_ids: list[UUID] | None = Field(None, description="Model flag UUIDs")
    model_rubric_ids: list[UUID] | None = Field(None, description="Model rubric UUIDs")
    model_position_ids: list[UUID] | None = Field(None, description="Model position UUIDs")


class EvalFieldError(BaseModel):
    """Per-field error from value resolution."""

    field: str = Field(..., description="Field name that has the error")
    message: str = Field(..., description="Human-readable error message")


class EvalResultItem(BaseModel):
    """Per-item result within a bulk create/update response."""

    success: bool = Field(..., description="Whether the operation succeeded")
    eval_id: UUID | None = Field(None, description="Eval UUID")
    message: str = Field(..., description="Human-readable result message")
    errors: list[EvalFieldError] | None = Field(None, description="List of per-field errors")


class CreateEvalApiResponse(BaseModel):
    """Response model for bulk create eval endpoint."""

    results: list[EvalResultItem] = Field(..., description="List of operation results")


async def create_eval_impl(
    pool: asyncpg.Pool,
    redis: Redis,
    *,
    profile_id: UUID,
    items: list,
    session_id: UUID | None = None,
    draft_id: UUID | None = None,
    group_id: UUID | None = None,
) -> dict:
    """Eval bulk create using composable infra functions.

    Flow:
      1. resolve_profile_identity_context → role, department_ids
      2. compute_can_create — single check (applies to all items)
      3. Per-item value resolution (raw → ID, required field enforcement)
      4. Single transaction: create_eval_artifact + denormalized snapshot per item
      5. invalidate_tags
    """
    from app.infra.eval.permissions import compute_can_create

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

    if not compute_can_create(user_role=profile.role):
        raise HTTPException(
            status_code=403,
            detail="You don't have permission to create evals.",
        )

    # ── Step 3: Per-item value resolution ──────────────────────────────

    has_errors = False
    error_results: list[EvalResultItem] = []

    async with pool.acquire() as conn:
        for idx, item in enumerate(items):
            item_errors = await resolve_eval_values(conn, redis, item, is_create=True)
            if item_errors:
                has_errors = True
                error_results.append(
                    EvalResultItem(
                        success=False,
                        message=f"Item {idx}: Validation errors",
                        errors=item_errors,
                    )
                )
            else:
                error_results.append(EvalResultItem(success=True, message="Validated"))

    if has_errors:
        return CreateEvalApiResponse(results=error_results)

    # ── Step 4: Single transaction ─────────────────────────────────────

    results: list[EvalResultItem] = []

    for item in items:
        # Create denormalized snapshot OUTSIDE transaction (read-only hydration)
        evals_resource_id = await create_denormalized_snapshot(
            pool,
            redis,
            id=item.id,
            name_id=item.name_id,
            description_id=item.description_id,
            department_ids=item.department_ids,
            model_ids=item.model_ids,
            model_rubric_ids=item.model_rubric_ids,
            model_flag_ids=item.model_flag_ids,
            model_position_ids=item.model_position_ids,
        )

        # Artifact create inside transaction
        async with pool.acquire() as conn:
            async with conn.transaction():
                result = await create_eval_artifact(
                    conn,
                    id=item.id,
                    name_id=item.name_id,
                    description_id=item.description_id,
                    department_ids=item.department_ids,
                    flag_ids=item.flag_ids,
                    model_ids=item.model_ids,
                    model_flag_ids=item.model_flag_ids,
                    model_rubric_ids=item.model_rubric_ids,
                    model_position_ids=item.model_position_ids,
                    eval_ids=[evals_resource_id],
                )

        results.append(
            EvalResultItem(
                success=True,
                eval_id=result.id,
                message="Eval created successfully",
            )
        )

    # ── Step 5: Invalidate cache ───────────────────────────────────────

    await invalidate_tags(["evals"], redis=redis)

    return CreateEvalApiResponse(results=results)
