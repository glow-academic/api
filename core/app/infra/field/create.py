"""Field create logic — composable infra architecture.

Composes existing black-box tools:
  1. resolve_profile_identity_context — profile (role, departments)
  2. compute_can_create — permission check
  3. resolve_field_values — raw value → ID resolution
  4. create_field_artifact — junction writes
  5. create_denormalized_snapshot — fields_resource snapshot
"""

from __future__ import annotations

from uuid import UUID

import asyncpg
from fastapi import HTTPException
from redis.asyncio import Redis

from app.infra.field.permissions_context import (
    create_denormalized_snapshot,
    resolve_field_values,
)
from app.infra.profile_identity_context import resolve_profile_identity_context
from app.tools.artifacts.field.create import (
    create_field as create_field_artifact,
)
from app.utils.cache.invalidate_tags import invalidate_tags


from app.infra.field.types import (
    CreateFieldApiRequest,
    CreateFieldItem,
    FieldFieldError,
    FieldResultItem,
    CreateFieldApiResponse,
)


async def create_field_impl(
    pool: asyncpg.Pool,
    redis: Redis,
    *,
    profile_id: UUID,
    request: CreateFieldApiRequest,
    session_id: UUID | None = None,
    draft_id: UUID | None = None,
    group_id: UUID | None = None,
    soft: bool = False,
) -> CreateFieldApiResponse:
    """Field bulk create using composable infra functions.

    Flow:
      1. resolve_profile_identity_context → role, department_ids
      2. compute_can_create — single check (applies to all items)
      3. Per-item value resolution (raw → ID, required field enforcement)
      4. Single transaction: create_field_artifact + denormalized snapshot per item
      5. invalidate_tags
    """
    from app.infra.field.permissions import compute_can_create

    items = request.fields

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
        role_level=profile.role_level, role_permissions=profile.role_permissions,
        department_ids=requested_department_ids or None,
    ):
        raise HTTPException(
            status_code=403,
            detail="You don't have permission to create fields.",
        )

    # ── Step 3: Per-item value resolution ──────────────────────────────

    has_errors = False
    error_results: list[FieldResultItem] = []

    async with pool.acquire() as conn:
        for idx, item in enumerate(items):
            item_errors = await resolve_field_values(conn, redis, item, is_create=True)
            if item_errors:
                has_errors = True
                error_results.append(
                    FieldResultItem(
                        success=False,
                        message=f"Item {idx}: Validation errors",
                        errors=item_errors,
                    )
                )
            else:
                error_results.append(FieldResultItem(success=True, message="Validated"))

    if has_errors:
        return CreateFieldApiResponse(results=error_results)

    # ── Step 4: Single transaction ─────────────────────────────────────

    results: list[FieldResultItem] = []

    for item in items:
        # Create denormalized snapshot OUTSIDE transaction (read-only hydration)
        fields_resource_id = await create_denormalized_snapshot(
            pool,
            redis,
            id=item.resource_id,
            name_id=item.name_id,
            description_id=item.description_id,
            department_ids=item.department_ids,
            conditional_parameter_ids=item.conditional_parameter_ids,
        )

        # Artifact create inside transaction
        async with pool.acquire() as conn:
            async with conn.transaction():
                # Combine existing flag_id with active_flag_id
                combined_flag_ids = []
                if item.flag_id:
                    combined_flag_ids.append(item.flag_id)
                if item.active_flag_id:
                    combined_flag_ids.append(item.active_flag_id)

                result = await create_field_artifact(
                    conn,
                    id=item.id,
                    name_id=item.name_id,
                    description_id=item.description_id,
                    department_ids=item.department_ids,
                    flag_ids=combined_flag_ids or None,
                    conditional_parameter_ids=item.conditional_parameter_ids,
                    field_ids=[fields_resource_id],
                    soft=soft,
                )

        results.append(
            FieldResultItem(
                success=True,
                field_id=result.id,
                message="Field created successfully",
            )
        )

    # ── Step 5: Invalidate cache ───────────────────────────────────────

    await invalidate_tags(["fields"], redis=redis)

    return CreateFieldApiResponse(results=results)
