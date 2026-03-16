"""Model create logic — composable infra architecture.

Composes existing black-box tools:
  1. resolve_profile_identity_context — profile (role, departments)
  2. compute_can_create — permission check
  3. resolve_model_values — raw value → ID resolution
  4. create_model_artifact — junction writes
  5. create_denormalized_snapshot — models_resource snapshot
"""

from __future__ import annotations

from uuid import UUID

import asyncpg
from fastapi import HTTPException
from pydantic import BaseModel, Field
from redis.asyncio import Redis

from app.infra.model.permissions_context import (
    create_denormalized_snapshot,
    resolve_model_values,
)
from app.infra.profile_identity_context import resolve_profile_identity_context
from app.tools.artifacts.model.create import (
    create_model as create_model_artifact,
)
from app.utils.cache.invalidate_tags import invalidate_tags


class CreateModelItem(BaseModel):
    """Single model item for create — no model_id.

    Required fields (name): provide ID or value.
    """

    id: UUID | None = Field(None, description="Optional pre-assigned identifier")

    # Dual-mode: name
    name_id: UUID | None = Field(None, description="Name resource identifier")
    name: str | None = Field(None, description="Display name value")
    # Dual-mode: description
    description_id: UUID | None = Field(None, description="Description resource identifier")
    description: str | None = Field(None, description="Description text value")
    # Dual-mode: departments (match by name)
    department_ids: list[UUID] | None = Field(None, description="Department identifiers")
    departments: list[str] | None = Field(None, description="Department names to match")
    # ID-only fields
    flag_ids: list[UUID] | None = Field(None, description="Flag option identifiers")
    modality_ids: list[UUID] | None = Field(None, description="Modality identifiers")
    pricing_ids: list[UUID] | None = Field(None, description="Pricing tier identifiers")
    provider_ids: list[UUID] | None = Field(None, description="Provider identifiers")
    quality_ids: list[UUID] | None = Field(None, description="Quality level identifiers")
    reasoning_level_ids: list[UUID] | None = Field(None, description="Reasoning level identifiers")
    temperature_level_ids: list[UUID] | None = Field(None, description="Temperature level identifiers")
    value_ids: list[UUID] | None = Field(None, description="Value resource identifiers")
    voice_ids: list[UUID] | None = Field(None, description="Voice identifiers")
    model_ids: list[UUID] | None = Field(None, description="Related model identifiers")


class ModelFieldError(BaseModel):
    """Per-field error from value resolution."""

    field: str = Field(..., description="Field name that caused the error")
    message: str = Field(..., description="Error message describing the issue")


class ModelResultItem(BaseModel):
    """Per-item result within a bulk create/update response."""

    success: bool = Field(..., description="Whether the operation succeeded")
    model_id: UUID | None = Field(None, description="Model unique identifier")
    message: str = Field(..., description="Result message")
    errors: list[ModelFieldError] | None = Field(None, description="List of field-level errors")


class CreateModelApiResponse(BaseModel):
    """Response model for bulk create model endpoint."""

    results: list[ModelResultItem] = Field(..., description="List of operation results")


async def create_model_impl(
    pool: asyncpg.Pool,
    redis: Redis,
    *,
    profile_id: UUID,
    items: list,
    session_id: UUID | None = None,
    draft_id: UUID | None = None,
    group_id: UUID | None = None,
) -> dict:
    """Model bulk create using composable infra functions.

    Flow:
      1. resolve_profile_identity_context → role, department_ids
      2. compute_can_create — single check (applies to all items)
      3. Per-item value resolution (raw → ID, required field enforcement)
      4. Single transaction: create_model_artifact + denormalized snapshot per item
      5. invalidate_tags
    """
    from app.infra.model.permissions import compute_can_create

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
        department_ids=profile.department_ids,
    ):
        raise HTTPException(
            status_code=403,
            detail="You don't have permission to create models.",
        )

    # ── Step 3: Per-item value resolution ──────────────────────────────

    has_errors = False
    error_results: list[ModelResultItem] = []

    async with pool.acquire() as conn:
        for idx, item in enumerate(items):
            item_errors = await resolve_model_values(conn, redis, item, is_create=True)
            if item_errors:
                has_errors = True
                error_results.append(
                    ModelResultItem(
                        success=False,
                        message=f"Item {idx}: Validation errors",
                        errors=item_errors,
                    )
                )
            else:
                error_results.append(ModelResultItem(success=True, message="Validated"))

    if has_errors:
        return CreateModelApiResponse(results=error_results)

    # ── Step 4: Single transaction ─────────────────────────────────────

    results: list[ModelResultItem] = []

    for item in items:
        # Create denormalized snapshot OUTSIDE transaction (read-only hydration)
        models_resource_id = await create_denormalized_snapshot(
            pool,
            redis,
            id=item.id,
            name_id=item.name_id,
            description_id=item.description_id,
            department_ids=item.department_ids,
            provider_ids=item.provider_ids,
            temperature_level_ids=item.temperature_level_ids,
            reasoning_level_ids=item.reasoning_level_ids,
            quality_ids=item.quality_ids,
            voice_ids=item.voice_ids,
            modality_ids=item.modality_ids,
            value_ids=item.value_ids,
        )

        # Artifact create inside transaction
        async with pool.acquire() as conn:
            async with conn.transaction():
                result = await create_model_artifact(
                    conn,
                    id=item.id,
                    name_id=item.name_id,
                    description_id=item.description_id,
                    department_ids=item.department_ids,
                    flag_ids=item.flag_ids,
                    modality_ids=item.modality_ids,
                    model_ids=[models_resource_id],
                    pricing_ids=item.pricing_ids,
                    provider_ids=item.provider_ids,
                    quality_ids=item.quality_ids,
                    reasoning_level_ids=item.reasoning_level_ids,
                    temperature_level_ids=item.temperature_level_ids,
                    value_ids=item.value_ids,
                    voice_ids=item.voice_ids,
                )

        results.append(
            ModelResultItem(
                success=True,
                model_id=result.id,
                message="Model created successfully",
            )
        )

    # ── Step 5: Invalidate cache ───────────────────────────────────────

    await invalidate_tags(["models"], redis=redis)

    return CreateModelApiResponse(results=results)
