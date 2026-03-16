"""Department update logic — composable infra architecture.

Composes existing black-box tools:
  1. resolve_profile_identity_context — profile (role, departments)
  2. resolve_department_permissions_context — per-item access + edit check
  3. resolve_department_values — raw value → ID resolution
  4. update_department_artifact — junction writes (partial update)
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
    resolve_department_permissions_context,
    resolve_department_values,
)
from app.infra.profile_identity_context import resolve_profile_identity_context
from app.tools.artifacts.department.get import (
    get_departments as get_department_artifacts,
)
from app.tools.artifacts.department.update import (
    _UNSET,
)
from app.tools.artifacts.department.update import (
    update_department as update_department_artifact,
)
from app.utils.cache.invalidate_tags import invalidate_tags


async def update_department_impl(
    pool: asyncpg.Pool,
    redis: Redis,
    *,
    profile_id: UUID,
    items: list,
    session_id: UUID | None = None,
    draft_id: UUID | None = None,
    group_id: UUID | None = None,
) -> dict:
    """Department bulk update using composable infra functions.

    Flow:
      1. resolve_profile_identity_context → role, department_ids
      2. Per-item: resolve_department_permissions_context → exists + compute_can_edit
      3. Per-item value resolution (raw → ID, no required field enforcement)
      4. Single transaction: update_department_artifact + denormalized snapshot per item
      5. invalidate_tags
      6. perform_keycloak_sync (non-fatal)
    """
    from app.infra.department.permissions import compute_can_edit
    from app.infra.department.types import (
        DepartmentResultItem,
        UpdateDepartmentApiResponse,
    )

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

    # ── Step 2: Per-item permission check ──────────────────────────────

    for idx, item in enumerate(items):
        async with pool.acquire() as conn:
            perms = await resolve_department_permissions_context(
                conn, item.department_id
            )
        if not perms.exists:
            raise HTTPException(
                status_code=404,
                detail=f"Item {idx}: Department {item.department_id} not found.",
            )
        if not compute_can_edit(
            user_role=profile.role,
            usage_count=perms.usage_count,
        ):
            raise HTTPException(
                status_code=403,
                detail=f"Item {idx}: You don't have permission to update this department.",
            )

    # ── Step 3: Per-item value resolution ──────────────────────────────

    has_errors = False
    error_results: list[DepartmentResultItem] = []

    for idx, item in enumerate(items):
        async with pool.acquire() as conn:
            item_errors = await resolve_department_values(
                conn, redis, item, is_create=False
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
        return UpdateDepartmentApiResponse(results=error_results)

    # ── Step 4: Single transaction ─────────────────────────────────────

    results: list[DepartmentResultItem] = []
    saved_department_ids: list[UUID] = []

    for item in items:
        # Fetch existing junction IDs so snapshot is always complete
        async with pool.acquire() as conn:
            existing = await get_department_artifacts(
                conn,
                [item.department_id],
                names=True,
                descriptions=True,
                settings=True,
            )
        if existing:
            art = existing[0]
            eff_name_id = item.name_id or (art.name_ids[0] if art.name_ids else None)
            eff_desc_id = item.description_id or (
                art.description_ids[0] if art.description_ids else None
            )
            eff_setting_ids = (
                item.settings_ids
                if item.settings_ids is not None
                else list(art.settings_ids or [])
            )
        else:
            eff_name_id = item.name_id
            eff_desc_id = item.description_id
            eff_setting_ids = item.settings_ids

        # Create denormalized snapshot OUTSIDE transaction (read-only hydration)
        departments_resource_id = await create_denormalized_snapshot(
            pool,
            redis,
            name_id=eff_name_id,
            description_id=eff_desc_id,
            setting_ids=eff_setting_ids,
        )

        # Artifact update inside transaction
        async with pool.acquire() as conn:
            async with conn.transaction():
                await update_department_artifact(
                    conn,
                    item.department_id,
                    name_id=item.name_id if item.name_id else _UNSET,
                    description_id=item.description_id
                    if item.description_id
                    else _UNSET,
                    department_ids=[departments_resource_id],
                    flag_ids=[item.active_flag_id] if item.active_flag_id else None,
                    settings_ids=item.settings_ids,
                )

        saved_department_ids.append(item.department_id)
        results.append(
            DepartmentResultItem(
                success=True,
                department_id=item.department_id,
                message="Department updated successfully",
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
            pass  # Non-fatal — sync failures should not block update

    return UpdateDepartmentApiResponse(results=results)
