"""Department create logic — composable infra architecture.

Composes existing black-box tools:
  1. resolve_profile_identity_context — profile (role, departments)
  2. compute_can_create — permission check
  3. resolve_department_values — raw value → ID resolution
  4. create_department_artifact — junction writes
  5. create_denormalized_snapshot — departments_resource snapshot
  6. perform_keycloak_sync — sync department to Keycloak (non-fatal)
"""

from __future__ import annotations

from uuid import UUID

import asyncpg
from fastapi import HTTPException
from pydantic import BaseModel, Field
from redis.asyncio import Redis

from app.infra.department.permissions_context import (
    create_denormalized_snapshot,
    resolve_department_values,
)
from app.infra.profile_identity_context import resolve_profile_identity_context
from app.tools.artifacts.department.create import (
    create_department as create_department_artifact,
)
from app.utils.cache.invalidate_tags import invalidate_tags


class CreateDepartmentItem(BaseModel):
    """Single department item for create — no department_id.

    Required fields (name): provide ID or value.
    """

    id: UUID | None = Field(None, description="Optional preset UUID for the new department")

    # Required single-select — provide ID or value
    name_id: UUID | None = Field(None, description="UUID of the name resource")
    name: str | None = Field(None, description="Name value to resolve or create")
    # Optional single-select — provide ID or value
    description_id: UUID | None = Field(None, description="UUID of the description resource")
    description: str | None = Field(None, description="Description value to resolve or create")
    active_flag_id: UUID | None = Field(None, description="UUID of the active flag option")
    active_flag: bool | None = Field(None, description="Whether the department is active")
    # ID-only fields
    settings_ids: list[UUID] | None = Field(None, description="Setting UUIDs to assign")
    department_ids: list[UUID] | None = Field(None, description="Sub-department UUIDs to assign")


class DepartmentFieldError(BaseModel):
    """Per-field error from value resolution."""

    field: str = Field(..., description="Name of the field that failed validation")
    message: str = Field(..., description="Validation error message")


class DepartmentResultItem(BaseModel):
    """Per-item result within a bulk create/update response."""

    success: bool = Field(..., description="Whether the operation succeeded")
    department_id: UUID | None = Field(None, description="UUID of the created department")
    message: str = Field(..., description="Result message")
    errors: list[DepartmentFieldError] | None = Field(None, description="Per-field validation errors")


class CreateDepartmentApiResponse(BaseModel):
    """Response model for bulk create department endpoint."""

    results: list[DepartmentResultItem] = Field(..., description="Per-item creation results")


async def create_department_impl(
    pool: asyncpg.Pool,
    redis: Redis,
    *,
    profile_id: UUID,
    items: list,
    session_id: UUID | None = None,
    draft_id: UUID | None = None,
    group_id: UUID | None = None,
) -> dict:
    """Department bulk create using composable infra functions.

    Flow:
      1. resolve_profile_identity_context → role, department_ids
      2. compute_can_create — single check (applies to all items)
      3. Per-item value resolution (raw → ID, required field enforcement)
      4. Single transaction: create_department_artifact + denormalized snapshot per item
      5. invalidate_tags
      6. perform_keycloak_sync (non-fatal)
    """
    from app.infra.department.permissions import compute_can_create

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
            detail="You don't have permission to create departments.",
        )

    # ── Step 3: Per-item value resolution ──────────────────────────────

    has_errors = False
    error_results: list[DepartmentResultItem] = []

    for idx, item in enumerate(items):
        async with pool.acquire() as conn:
            item_errors = await resolve_department_values(
                conn, redis, item, is_create=True
            )
        if item_errors:
            has_errors = True
            error_results.append(
                DepartmentResultItem(
                    success=False,
                    message=f"Item {idx}: Validation errors",
                    errors=item_errors,
                )
            )
        else:
            error_results.append(
                DepartmentResultItem(success=True, message="Validated")
            )

    if has_errors:
        return CreateDepartmentApiResponse(results=error_results)

    # ── Step 4: Single transaction ─────────────────────────────────────

    results: list[DepartmentResultItem] = []
    saved_department_ids: list[UUID] = []

    for item in items:
        # Create denormalized snapshot OUTSIDE transaction (read-only hydration)
        departments_resource_id = await create_denormalized_snapshot(
            pool,
            redis,
            id=item.id,
            name_id=item.name_id,
            description_id=item.description_id,
            setting_ids=item.settings_ids,
        )

        # Artifact create inside transaction
        async with pool.acquire() as conn:
            async with conn.transaction():
                result = await create_department_artifact(
                    conn,
                    id=item.id,
                    name_id=item.name_id,
                    description_id=item.description_id,
                    department_ids=[departments_resource_id],
                    flag_ids=[item.active_flag_id] if item.active_flag_id else None,
                    settings_ids=item.settings_ids,
                )

        saved_department_ids.append(result.id)
        results.append(
            DepartmentResultItem(
                success=True,
                department_id=result.id,
                message="Department created successfully",
            )
        )

    # ── Step 5: Invalidate cache ───────────────────────────────────────

    await invalidate_tags(["departments"], redis=redis)

    # ── Step 6: Keycloak sync (non-fatal) ──────────────────────────────

    from app.infra.identity.keycloak_sync import perform_keycloak_sync

    for department_id in saved_department_ids:
        try:
            await perform_keycloak_sync(department_id=str(department_id))
        except Exception:
            pass  # Non-fatal — sync failures should not block create

    return CreateDepartmentApiResponse(results=results)
