"""Auth update logic — composable infra architecture.

Composes existing black-box tools:
  1. resolve_profile_identity_context — profile (role, departments)
  2. resolve_auth_permissions_context — per-item access + edit check
  3. resolve_auth_values — raw value → ID resolution
  4. update_auth_artifact — junction writes (partial update)
  5. create_denormalized_snapshot — auths_resource snapshot
  6. perform_keycloak_sync — sync auth state (non-fatal)
"""

from __future__ import annotations

from uuid import UUID

import asyncpg
from fastapi import HTTPException
from redis.asyncio import Redis

from app.infra.auth.permissions_context import (
    create_denormalized_snapshot,
    resolve_auth_permissions_context,
    resolve_auth_values,
)
from app.infra.identity.keycloak_sync import perform_keycloak_sync
from app.infra.profile_identity_context import resolve_profile_identity_context
from app.tools.artifacts.auth.update import (
    _UNSET,
)
from app.tools.artifacts.auth.update import (
    update_auth as update_auth_artifact,
)
from app.utils.cache.invalidate_tags import invalidate_tags
from app.utils.logging.db_logger import get_logger

logger = get_logger(__name__)


async def update_auth_impl(
    pool: asyncpg.Pool,
    redis: Redis,
    *,
    profile_id: UUID,
    items: list,
    session_id: UUID | None = None,
    draft_id: UUID | None = None,
    group_id: UUID | None = None,
) -> dict:
    """Auth bulk update using composable infra functions.

    Flow:
      1. resolve_profile_identity_context → role, department_ids
      2. Per-item: resolve_auth_permissions_context → exists + compute_can_edit
      3. Per-item value resolution (raw → ID, no required field enforcement)
      4. Single transaction: update_auth_artifact + denormalized snapshot per item
      5. invalidate_tags
      6. perform_keycloak_sync (non-fatal)
    """
    from app.infra.auth.permissions import compute_can_edit
    from app.infra.auth.types import (
        AuthResultItem,
        UpdateAuthApiResponse,
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
            perms = await resolve_auth_permissions_context(conn, item.auth_id)
        if not perms.exists:
            raise HTTPException(
                status_code=404,
                detail=f"Item {idx}: Auth {item.auth_id} not found.",
            )
        if not compute_can_edit(
            user_role=profile.role,
            active_settings_count=perms.active_settings_count,
        ):
            raise HTTPException(
                status_code=403,
                detail=f"Item {idx}: You don't have permission to update this auth.",
            )

    # ── Step 3: Per-item value resolution ──────────────────────────────

    has_errors = False
    error_results: list[AuthResultItem] = []

    for idx, item in enumerate(items):
        async with pool.acquire() as conn:
            item_errors = await resolve_auth_values(conn, redis, item, is_create=False)
        if item_errors:
            has_errors = True
            error_results.append(
                AuthResultItem(
                    success=False,
                    message=f"Item {idx}: Validation errors",
                    errors=item_errors,
                )
            )
        else:
            error_results.append(AuthResultItem(success=True, message="Validated"))

    if has_errors:
        return UpdateAuthApiResponse(results=error_results)

    # ── Step 4: Single transaction ─────────────────────────────────────

    results: list[AuthResultItem] = []

    for item in items:
        # Create denormalized snapshot OUTSIDE transaction (read-only hydration)
        auths_resource_id = await create_denormalized_snapshot(
            pool,
            redis,
            name_id=item.name_id,
            description_id=item.description_id,
            department_ids=item.department_ids,
            slug_id=item.slug_id,
            protocol_ids=item.protocol_ids,
        )

        # Artifact update inside transaction
        async with pool.acquire() as conn:
            async with conn.transaction():
                await update_auth_artifact(
                    conn,
                    item.auth_id,
                    name_id=item.name_id if item.name_id else _UNSET,
                    description_id=item.description_id
                    if item.description_id
                    else _UNSET,
                    slug_id=item.slug_id if item.slug_id else _UNSET,
                    department_ids=item.department_ids,
                    flag_ids=[item.active_flag_id] if item.active_flag_id else None,
                    item_ids=item.item_ids,
                    protocol_ids=item.protocol_ids,
                    auth_ids=[auths_resource_id]
                    if auths_resource_id
                    else item.auth_resource_ids,
                )

        results.append(
            AuthResultItem(
                success=True,
                auth_id=item.auth_id,
                message="Auth updated successfully",
            )
        )

    # ── Step 5: Invalidate cache ───────────────────────────────────────

    await invalidate_tags(["auths"], redis=redis)

    # ── Step 6: Keycloak sync (non-fatal) ──────────────────────────────

    try:
        await perform_keycloak_sync(department_id=None)
    except Exception:
        logger.warning("Keycloak sync failed after auth update (non-fatal)")

    return UpdateAuthApiResponse(results=results)
