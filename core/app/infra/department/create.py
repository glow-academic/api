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


from app.infra.department.types import (
    CreateDepartmentItem,
    DepartmentFieldError,
    DepartmentResultItem,
    CreateDepartmentApiResponse,
)


async def create_department_impl(
    pool: asyncpg.Pool,
    redis: Redis,
    *,
    profile_id: UUID,
    items: list,
    session_id: UUID | None = None,
    draft_id: UUID | None = None,
    group_id: UUID | None = None,
    soft: bool = False,
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

    if not compute_can_create(role_level=profile.role_level, role_permissions=profile.role_permissions):
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
            id=item.resource_id,
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
                    soft=soft,
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
