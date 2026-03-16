"""Provider create logic — composable infra architecture.

Composes existing black-box tools:
  1. resolve_profile_identity_context — profile (role, departments)
  2. compute_can_create — permission check
  3. resolve_provider_values — raw value → ID resolution
  4. create_provider_artifact — junction writes
  5. create_denormalized_snapshot — providers_resource snapshot
"""

from __future__ import annotations

from uuid import UUID

import asyncpg
from fastapi import HTTPException
from pydantic import BaseModel, Field
from redis.asyncio import Redis

from app.infra.profile_identity_context import resolve_profile_identity_context
from app.infra.provider.permissions_context import (
    create_denormalized_snapshot,
    resolve_provider_values,
)
from app.tools.artifacts.provider.create import (
    create_provider as create_provider_artifact,
)
from app.utils.cache.invalidate_tags import invalidate_tags


class CreateProviderItem(BaseModel):
    """Single provider item for create — no provider_id."""

    id: UUID | None = Field(None, description="Optional pre-assigned identifier")

    # Required single-select — provide ID or value
    name_id: UUID | None = Field(None, description="Name resource identifier")
    name: str | None = Field(None, description="Display name value")
    # Optional single-select — provide ID or value
    description_id: UUID | None = Field(None, description="Description resource identifier")
    description: str | None = Field(None, description="Description text value")
    active_flag_id: UUID | None = Field(None, description="Active flag option identifier")
    active_flag: bool | None = Field(None, description="Whether the provider is active")
    # Optional multi-select — provide IDs or values
    department_ids: list[UUID] | None = Field(None, description="Department identifiers")
    departments: list[str] | None = Field(None, description="Department names to match")
    # ID-only fields
    endpoint_ids: list[UUID] | None = Field(None, description="Endpoint resource identifiers")
    key_ids: list[UUID] | None = Field(None, description="API key resource identifiers")
    value_ids: list[UUID] | None = Field(None, description="Value resource identifiers")


class ProviderFieldError(BaseModel):
    """Per-field error from value resolution."""

    field: str = Field(..., description="Field name that caused the error")
    message: str = Field(..., description="Error message describing the issue")


class ProviderResultItem(BaseModel):
    """Per-item result within a bulk create/update response."""

    success: bool = Field(..., description="Whether the operation succeeded")
    provider_id: UUID | None = Field(None, description="Provider unique identifier")
    message: str = Field(..., description="Result message")
    errors: list[ProviderFieldError] | None = Field(None, description="List of field-level errors")


class CreateProviderApiResponse(BaseModel):
    """Response model for bulk create provider endpoint."""

    results: list[ProviderResultItem] = Field(..., description="List of operation results")


async def create_provider_impl(
    pool: asyncpg.Pool,
    redis: Redis,
    *,
    profile_id: UUID,
    items: list,
    session_id: UUID | None = None,
    draft_id: UUID | None = None,
    group_id: UUID | None = None,
) -> dict:
    """Provider bulk create using composable infra functions.

    Flow:
      1. resolve_profile_identity_context → role, department_ids
      2. compute_can_create — single check (applies to all items)
      3. Per-item value resolution (raw → ID, required field enforcement)
      4. Single transaction: create_provider_artifact + denormalized snapshot per item
      5. invalidate_tags
    """
    from app.infra.provider.permissions import compute_can_create

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
            detail="You don't have permission to create providers.",
        )

    # ── Step 3: Per-item value resolution ──────────────────────────────

    has_errors = False
    error_results: list[ProviderResultItem] = []

    async with pool.acquire() as conn:
        for idx, item in enumerate(items):
            item_errors = await resolve_provider_values(
                conn, redis, item, is_create=True
            )
            if item_errors:
                has_errors = True
                error_results.append(
                    ProviderResultItem(
                        success=False,
                        message=f"Item {idx}: Validation errors",
                        errors=item_errors,
                    )
                )
            else:
                error_results.append(
                    ProviderResultItem(success=True, message="Validated")
                )

    if has_errors:
        return CreateProviderApiResponse(results=error_results)

    # ── Step 4: Single transaction ─────────────────────────────────────

    results: list[ProviderResultItem] = []

    for item in items:
        # Create denormalized snapshot OUTSIDE transaction (read-only hydration)
        providers_resource_id = await create_denormalized_snapshot(
            pool,
            redis,
            id=item.id,
            name_id=item.name_id,
            description_id=item.description_id,
            department_ids=item.department_ids,
        )

        # Artifact create inside transaction
        async with pool.acquire() as conn:
            async with conn.transaction():
                result = await create_provider_artifact(
                    conn,
                    id=item.id,
                    name_id=item.name_id,
                    description_id=item.description_id,
                    department_ids=item.department_ids,
                    endpoint_ids=item.endpoint_ids,
                    flag_ids=[item.active_flag_id] if item.active_flag_id else None,
                    key_ids=item.key_ids,
                    provider_ids=[providers_resource_id],
                    value_ids=item.value_ids,
                )

        results.append(
            ProviderResultItem(
                success=True,
                provider_id=result.id,
                message="Provider created successfully",
            )
        )

    # ── Step 5: Invalidate cache ───────────────────────────────────────

    await invalidate_tags(["providers"], redis=redis)

    return CreateProviderApiResponse(results=results)
