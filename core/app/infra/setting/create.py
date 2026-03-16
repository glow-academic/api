"""Setting create logic — composable infra architecture.

Composes existing black-box tools:
  1. resolve_profile_identity_context — profile (role, departments)
  2. Permission check — role-based
  3. resolve_setting_values — raw value → ID resolution
  4. create_setting_artifact — junction writes
  5. create_denormalized_snapshot — settings_resource snapshot
"""

from __future__ import annotations

from uuid import UUID

import asyncpg
from fastapi import HTTPException
from pydantic import BaseModel, Field
from redis.asyncio import Redis

from app.infra.profile_identity_context import resolve_profile_identity_context
from app.infra.setting.permissions_context import (
    create_denormalized_snapshot,
    resolve_setting_values,
)
from app.tools.artifacts.setting.create import (
    create_setting as create_setting_artifact,
)
from app.utils.cache.invalidate_tags import invalidate_tags


class CreateSettingItem(BaseModel):
    """Single setting item for create — no setting_id.

    Required fields (name): provide ID or value.
    """

    id: UUID | None = Field(None, description="Optional preset UUID for the new setting")

    # Required single-select — provide ID or value
    name_id: UUID | None = Field(None, description="UUID of the name resource")
    name: str | None = Field(None, description="Name value to resolve or create")
    # Optional single-select — provide ID or value
    description_id: UUID | None = Field(None, description="UUID of the description resource")
    description: str | None = Field(None, description="Description value to resolve or create")
    # Optional flag
    active_flag_id: UUID | None = Field(None, description="UUID of the active flag option")
    active_flag: bool | None = Field(None, description="Whether the setting is active")
    # Optional multi-select — provide IDs or values
    department_ids: list[UUID] | None = Field(None, description="Department UUIDs to assign")
    departments: list[str] | None = Field(None, description="Department names to resolve")
    color_ids: list[UUID] | None = Field(None, description="Color resource UUIDs")
    profile_ids: list[UUID] | None = Field(None, description="Profile UUIDs to assign")
    auth_ids: list[UUID] | None = Field(None, description="Auth provider UUIDs")
    provider_key_ids: list[UUID] | None = Field(None, description="Provider key UUIDs")
    auth_item_key_ids: list[UUID] | None = Field(None, description="Auth item key UUIDs")
    auth_item_value_ids: list[UUID] | None = Field(None, description="Auth item value UUIDs")
    system_ids: list[UUID] | None = Field(None, description="System UUIDs to assign")
    threshold_ids: list[UUID] | None = Field(None, description="Threshold UUIDs to assign")
    setting_resource_ids: list[UUID] | None = Field(None, description="Setting resource UUIDs")


class SettingFieldError(BaseModel):
    """Per-field error from value resolution."""

    field: str = Field(..., description="Name of the field that failed validation")
    message: str = Field(..., description="Validation error message")


class SettingResultItem(BaseModel):
    """Per-item result within a bulk create/update response."""

    success: bool = Field(..., description="Whether the operation succeeded")
    setting_id: UUID | None = Field(None, description="UUID of the created setting")
    message: str = Field(..., description="Result message")
    errors: list[SettingFieldError] | None = Field(None, description="Per-field validation errors")


class CreateSettingApiResponse(BaseModel):
    """Response model for bulk create setting endpoint."""

    results: list[SettingResultItem] = Field(..., description="Per-item creation results")


async def create_setting_impl(
    pool: asyncpg.Pool,
    redis: Redis,
    *,
    profile_id: UUID,
    items: list,
    session_id: UUID | None = None,
    draft_id: UUID | None = None,
    group_id: UUID | None = None,
) -> dict:
    """Setting bulk create using composable infra functions.

    Flow:
      1. resolve_profile_identity_context → role, department_ids
      2. Permission check — role-based (admin/superadmin)
      3. Per-item value resolution (raw → ID, required field enforcement)
      4. Single transaction: create_setting_artifact + denormalized snapshot per item
      5. invalidate_tags
    """
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

    if profile.role not in ("admin", "superadmin"):
        raise HTTPException(
            status_code=403,
            detail="You don't have permission to create settings.",
        )

    # ── Step 3: Per-item value resolution ──────────────────────────────

    has_errors = False
    error_results: list[SettingResultItem] = []

    for idx, item in enumerate(items):
        async with pool.acquire() as conn:
            item_errors = await resolve_setting_values(
                conn, redis, item, is_create=True
            )
        if item_errors:
            has_errors = True
            error_results.append(
                SettingResultItem(
                    success=False,
                    message=f"Item {idx}: Validation errors",
                    errors=item_errors,
                )
            )
        else:
            error_results.append(SettingResultItem(success=True, message="Validated"))

    if has_errors:
        return CreateSettingApiResponse(results=error_results)

    # ── Step 4: Single transaction ─────────────────────────────────────

    results: list[SettingResultItem] = []

    for item in items:
        # Create denormalized snapshot OUTSIDE transaction (read-only hydration)
        settings_resource_id = await create_denormalized_snapshot(
            pool,
            redis,
            id=item.id,
            name_id=item.name_id,
            description_id=item.description_id,
            department_ids=item.department_ids,
            provider_key_ids=item.provider_key_ids,
            auth_ids=item.auth_ids,
            system_ids=item.system_ids,
        )

        # Artifact create inside transaction
        async with pool.acquire() as conn:
            async with conn.transaction():
                result = await create_setting_artifact(
                    conn,
                    id=item.id,
                    name_id=item.name_id,
                    description_id=item.description_id,
                    department_ids=item.department_ids,
                    flag_ids=[item.active_flag_id] if item.active_flag_id else None,
                    color_ids=item.color_ids,
                    profile_ids=item.profile_ids,
                    auth_ids=item.auth_ids,
                    provider_key_ids=item.provider_key_ids,
                    auth_item_key_ids=item.auth_item_key_ids,
                    auth_item_value_ids=item.auth_item_value_ids,
                    system_ids=item.system_ids,
                    threshold_ids=item.threshold_ids,
                    setting_ids=[settings_resource_id]
                    if settings_resource_id
                    else item.setting_resource_ids,
                )

        results.append(
            SettingResultItem(
                success=True,
                setting_id=result.id,
                message="Setting created successfully",
            )
        )

    # ── Step 5: Invalidate cache ───────────────────────────────────────

    await invalidate_tags(["settings"], redis=redis)

    return CreateSettingApiResponse(results=results)
