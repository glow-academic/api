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


from app.infra.profile.types import (
    CreateProfileItem,
    ProfileFieldError,
    ProfileResultItem,
    CreateProfileApiResponse,
)


async def create_profile_impl(
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

    if not compute_can_create(role_level=profile.role_level, role_permissions=profile.role_permissions, department_ids=None):
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
                    id=item.resource_id,
                    name_id=item.name_id,
                    department_ids=item.department_ids,
                    email_ids=item.email_ids,
                    role_id=item.role_id,
                )

                result = await create_profile_artifact(
                    conn,
                    id=item.id,
                    name_id=item.name_id,
                    request_limit_id=item.request_limit_id,
                    department_ids=item.department_ids,
                    flag_ids=[item.active_flag_id] if item.active_flag_id else None,
                    email_ids=item.email_ids,
                    role_ids=[item.role_id] if item.role_id else None,
                    profile_ids=[profiles_resource_id],
                    redis=redis,
                    soft=soft,
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
