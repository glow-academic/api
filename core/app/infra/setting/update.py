"""Setting update logic — composable infra architecture.

Composes existing black-box tools:
  1. resolve_profile_identity_context — profile (role, departments)
  2. resolve_setting_permissions_context — per-item access + edit check
  3. resolve_setting_values — raw value → ID resolution
  4. update_setting_artifact — junction writes (partial update)
  5. create_denormalized_snapshot — settings_resource snapshot
"""

from __future__ import annotations

from uuid import UUID

import asyncpg
from fastapi import HTTPException
from redis.asyncio import Redis

from app.infra.profile_identity_context import resolve_profile_identity_context
from app.infra.setting.permissions_context import (
    create_denormalized_snapshot,
    resolve_setting_permissions_context,
    resolve_setting_values,
)
from app.tools.artifacts.setting.get import (
    get_settings as get_setting_artifacts,
)
from app.tools.artifacts.setting.update import (
    _UNSET,
)
from app.tools.artifacts.setting.update import (
    update_setting as update_setting_artifact,
)
from app.utils.cache.invalidate_tags import invalidate_tags


async def update_setting_impl(
    pool: asyncpg.Pool,
    redis: Redis,
    *,
    profile_id: UUID,
    items: list,
    session_id: UUID | None = None,
    draft_id: UUID | None = None,
    group_id: UUID | None = None,
) -> dict:
    """Setting bulk update using composable infra functions.

    Flow:
      1. resolve_profile_identity_context → role, department_ids
      2. Per-item: resolve_setting_permissions_context → exists + compute_can_edit
      3. Per-item value resolution (raw → ID, no required field enforcement)
      4. Single transaction: update_setting_artifact + denormalized snapshot per item
      5. invalidate_tags
    """
    from app.infra.setting.permissions import compute_can_edit
    from app.infra.setting.types import (
        SettingResultItem,
        UpdateSettingApiResponse,
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
            perms = await resolve_setting_permissions_context(conn, item.setting_id)
        if not perms.exists:
            raise HTTPException(
                status_code=404,
                detail=f"Item {idx}: Setting {item.setting_id} not found.",
            )
        if not compute_can_edit(
            user_role=profile.role,
            setting_department_ids=perms.department_ids,
            user_department_ids=profile.department_ids,
        ):
            raise HTTPException(
                status_code=403,
                detail=f"Item {idx}: You don't have permission to update this setting.",
            )

    # ── Step 3: Per-item value resolution ──────────────────────────────

    has_errors = False
    error_results: list[SettingResultItem] = []

    for idx, item in enumerate(items):
        async with pool.acquire() as conn:
            item_errors = await resolve_setting_values(
                conn, redis, item, is_create=False
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
        return UpdateSettingApiResponse(results=error_results)

    # ── Step 4: Single transaction ─────────────────────────────────────

    results: list[SettingResultItem] = []

    for item in items:
        # Fetch existing junction IDs so snapshot is always complete
        async with pool.acquire() as conn:
            existing = await get_setting_artifacts(
                conn,
                [item.setting_id],
                names=True,
                descriptions=True,
                departments=True,
                provider_keys=True,
                auths=True,
                systems=True,
            )
        if existing:
            art = existing[0]
            eff_name_id = item.name_id or (art.name_ids[0] if art.name_ids else None)
            eff_desc_id = item.description_id or (
                art.description_ids[0] if art.description_ids else None
            )
            eff_department_ids = (
                item.department_ids
                if item.department_ids is not None
                else list(art.department_ids or [])
            )
            eff_provider_key_ids = (
                item.provider_key_ids
                if item.provider_key_ids is not None
                else list(art.provider_key_ids or [])
            )
            eff_auth_ids = (
                item.auth_ids if item.auth_ids is not None else list(art.auth_ids or [])
            )
            eff_system_ids = (
                item.system_ids
                if item.system_ids is not None
                else list(art.systems_ids or [])
            )
        else:
            eff_name_id = item.name_id
            eff_desc_id = item.description_id
            eff_department_ids = item.department_ids
            eff_provider_key_ids = item.provider_key_ids
            eff_auth_ids = item.auth_ids
            eff_system_ids = item.system_ids

        # Create denormalized snapshot OUTSIDE transaction (read-only hydration)
        settings_resource_id = await create_denormalized_snapshot(
            pool,
            redis,
            name_id=eff_name_id,
            description_id=eff_desc_id,
            department_ids=eff_department_ids,
            provider_key_ids=eff_provider_key_ids,
            auth_ids=eff_auth_ids,
            system_ids=eff_system_ids,
        )

        # Artifact update inside transaction
        async with pool.acquire() as conn:
            async with conn.transaction():
                await update_setting_artifact(
                    conn,
                    item.setting_id,
                    name_id=item.name_id if item.name_id else _UNSET,
                    description_id=item.description_id
                    if item.description_id
                    else _UNSET,
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
                setting_id=item.setting_id,
                message="Setting updated successfully",
            )
        )

    # ── Step 5: Invalidate cache ───────────────────────────────────────

    await invalidate_tags(["settings"], redis=redis)

    return UpdateSettingApiResponse(results=results)
