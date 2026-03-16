"""Profile update logic — composable infra architecture.

Composes existing black-box tools:
  1. resolve_profile_identity_context — profile (role, departments)
  2. resolve_profile_permissions_context — per-item access + edit check
  3. resolve_profile_values — raw value → ID resolution
  4. update_profile_artifact — junction writes (partial update)
  5. create_denormalized_snapshot — profiles_resource snapshot
"""

from __future__ import annotations

from uuid import UUID

import asyncpg
from fastapi import HTTPException
from redis.asyncio import Redis

from app.infra.profile.permissions_context import (
    create_denormalized_snapshot,
    resolve_profile_permissions_context,
    resolve_profile_values,
)
from app.infra.profile_identity_context import resolve_profile_identity_context
from app.tools.artifacts.profile.get import (
    get_profiles as get_profile_artifacts,
)
from app.tools.artifacts.profile.update import (
    _UNSET,
)
from app.tools.artifacts.profile.update import (
    update_profile as update_profile_artifact,
)
from app.utils.cache.invalidate_tags import invalidate_tags


async def update_profile_impl(
    pool: asyncpg.Pool,
    redis: Redis,
    *,
    profile_id: UUID,
    items: list,
    session_id: UUID | None = None,
    draft_id: UUID | None = None,
    group_id: UUID | None = None,
) -> dict:
    """Profile bulk update using composable infra functions.

    Flow:
      1. resolve_profile_identity_context → role, department_ids
      2. Per-item: resolve_profile_permissions_context → exists + compute_can_edit
      3. Per-item value resolution (raw → ID, no required field enforcement)
      4. Single transaction: update_profile_artifact + denormalized snapshot per item
      5. invalidate_tags
    """
    from app.infra.profile.permissions import compute_can_edit
    from app.infra.profile.types import (
        ProfileResultItem,
        UpdateProfileApiResponse,
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

    async with pool.acquire() as conn:
        for idx, item in enumerate(items):
            target_is_self = item.profile_id == profile_id
            perms = await resolve_profile_permissions_context(conn, item.profile_id)
            if not perms.exists:
                raise HTTPException(
                    status_code=404,
                    detail=f"Item {idx}: Profile {item.profile_id} not found.",
                )
            if not compute_can_edit(
                user_role=profile.role,
                target_is_self=target_is_self,
                target_department_ids=perms.department_ids,
                user_department_ids=profile.department_ids,
            ):
                raise HTTPException(
                    status_code=403,
                    detail=f"Item {idx}: You don't have permission to update this profile.",
                )

    # ── Step 3: Per-item value resolution ──────────────────────────────

    has_errors = False
    error_results: list[ProfileResultItem] = []

    async with pool.acquire() as conn:
        for idx, item in enumerate(items):
            item_errors = await resolve_profile_values(
                conn, redis, item, is_create=False
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
        return UpdateProfileApiResponse(results=error_results)

    # ── Step 4: Single transaction ─────────────────────────────────────

    results: list[ProfileResultItem] = []

    for item in items:
        # Fetch existing junction IDs so snapshot is always complete
        async with pool.acquire() as conn:
            existing = await get_profile_artifacts(
                conn,
                [item.profile_id],
                names=True,
                departments=True,
            )
        if existing:
            art = existing[0]
            eff_name_id = item.name_id or (art.name_ids[0] if art.name_ids else None)
            eff_department_ids = (
                item.department_ids
                if item.department_ids is not None
                else list(art.department_ids or [])
            )
        else:
            eff_name_id = item.name_id
            eff_department_ids = item.department_ids

        # Create denormalized snapshot OUTSIDE transaction (read-only hydration)
        async with pool.acquire() as conn:
            profiles_resource_id = await create_denormalized_snapshot(
                conn,
                redis,
                name_id=eff_name_id,
                department_ids=eff_department_ids,
            )

        # Artifact update inside transaction
        async with pool.acquire() as conn:
            async with conn.transaction():
                await update_profile_artifact(
                    conn,
                    item.profile_id,
                    name_id=item.name_id if item.name_id else _UNSET,
                    request_limit_id=item.request_limit_id
                    if item.request_limit_id
                    else _UNSET,
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
                profile_id=item.profile_id,
                message="Profile updated successfully",
            )
        )

    # ── Step 5: Invalidate cache ───────────────────────────────────────

    await invalidate_tags(["profiles"], redis=redis)

    return UpdateProfileApiResponse(results=results)
