"""Profile create logic — composable infra architecture.

Composes existing black-box tools:
  1. resolve_profile_identity_context — profile (role, departments)
  2. compute_can_create — permission check
  3. resolve_profile_values — raw value → ID resolution
  4. create_profile_artifact — junction writes
  5. create_denormalized_snapshot — profiles_resource snapshot
"""

from __future__ import annotations

from uuid import UUID

import asyncpg
from fastapi import HTTPException
from pydantic import BaseModel, Field
from redis.asyncio import Redis

from app.infra.profile.permissions_context import (
    create_denormalized_snapshot,
    resolve_profile_values,
)
from app.infra.profile_identity_context import resolve_profile_identity_context
from app.tools.artifacts.profile.create import (
    create_profile as create_profile_artifact,
)
from app.utils.cache.invalidate_tags import invalidate_tags


class CreateProfileItem(BaseModel):
    """Single profile item for create — no profile_id."""

    id: UUID | None = Field(None, description="Optional preset UUID for the new profile")

    # Required single-select — provide ID or value
    name_id: UUID | None = Field(None, description="UUID of the name resource")
    name: str | None = Field(None, description="Name value to resolve or create")
    # Optional single-select — provide IDs only
    request_limit_id: UUID | None = Field(None, description="UUID of the request limit resource")
    flag_id: UUID | None = Field(None, description="UUID of the flag option")
    # Optional multi-select — provide IDs or values
    department_ids: list[UUID] | None = Field(None, description="Department UUIDs to assign")
    departments: list[str] | None = Field(None, description="Department names to resolve")
    email_ids: list[UUID] | None = Field(None, description="Email resource UUIDs")
    role_ids: list[UUID] | None = Field(None, description="Role resource UUIDs")


class ProfileFieldError(BaseModel):
    """Per-field error from value resolution."""

    field: str = Field(..., description="Name of the field that failed validation")
    message: str = Field(..., description="Validation error message")


class ProfileResultItem(BaseModel):
    """Per-item result within a bulk create/update response."""

    success: bool = Field(..., description="Whether the operation succeeded")
    profile_id: UUID | None = Field(None, description="UUID of the created profile")
    message: str = Field(..., description="Result message")
    errors: list[ProfileFieldError] | None = Field(None, description="Per-field validation errors")


class CreateProfileApiResponse(BaseModel):
    """Response model for bulk create profile endpoint."""

    results: list[ProfileResultItem] = Field(..., description="Per-item creation results")


async def create_profile_impl(
    pool: asyncpg.Pool,
    redis: Redis,
    *,
    profile_id: UUID,
    items: list,
    session_id: UUID | None = None,
    draft_id: UUID | None = None,
    group_id: UUID | None = None,
) -> dict:
    """Profile bulk create using composable infra functions.

    Flow:
      1. resolve_profile_identity_context → role, department_ids
      2. compute_can_create — single check (applies to all items)
      3. Per-item value resolution (raw → ID, required field enforcement)
      4. Single transaction: create_profile_artifact + denormalized snapshot per item
      5. invalidate_tags
    """
    from app.infra.profile.permissions import compute_can_create

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
            detail="You don't have permission to create profiles.",
        )

    # ── Step 3: Per-item value resolution ──────────────────────────────

    has_errors = False
    error_results: list[ProfileResultItem] = []

    async with pool.acquire() as conn:
        for idx, item in enumerate(items):
            item_errors = await resolve_profile_values(
                conn, redis, item, is_create=True
            )
            if item_errors:
                has_errors = True
                error_results.append(
                    ProfileResultItem(
                        success=False,
                        message=f"Item {idx}: Validation errors",
                        errors=item_errors,
                    )
                )
            else:
                error_results.append(
                    ProfileResultItem(success=True, message="Validated")
                )

    if has_errors:
        return CreateProfileApiResponse(results=error_results)

    # ── Step 4: Single transaction ─────────────────────────────────────

    results: list[ProfileResultItem] = []

    async with pool.acquire() as conn:
        async with conn.transaction():
            for item in items:
                # Create denormalized snapshot
                profiles_resource_id = await create_denormalized_snapshot(
                    conn,
                    redis,
                    id=item.id,
                    name_id=item.name_id,
                    department_ids=item.department_ids,
                )

                result = await create_profile_artifact(
                    conn,
                    id=item.id,
                    name_id=item.name_id,
                    request_limit_id=item.request_limit_id,
                    department_ids=item.department_ids,
                    flag_ids=[item.flag_id] if item.flag_id else None,
                    email_ids=item.email_ids,
                    role_ids=item.role_ids,
                    profile_ids=[profiles_resource_id],
                    redis=redis,
                )

                results.append(
                    ProfileResultItem(
                        success=True,
                        profile_id=result.id,
                        message="Profile created successfully",
                    )
                )

    # ── Step 5: Invalidate cache ───────────────────────────────────────

    await invalidate_tags(["profiles"], redis=redis)

    return CreateProfileApiResponse(results=results)
