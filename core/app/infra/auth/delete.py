"""Auth delete logic — composable infra architecture.

Core delete function that composes existing black-box tools:
  1. resolve_profile_identity_context — profile (role)
  2. Per-item loop: permissions context + inline SQL for active_settings_count
  3. compute_can_delete — permission check
  4. delete_auths — bulk delete tool
  5. invalidate_tags — cache invalidation
  6. Keycloak sync — post-delete
"""

from __future__ import annotations

from uuid import UUID

import asyncpg
from fastapi import HTTPException
from redis.asyncio import Redis

from app.infra.auth.permissions import compute_can_delete
from app.infra.auth.permissions_context import (
    resolve_auth_permissions_context,
)
from app.infra.profile_identity_context import resolve_profile_identity_context
from app.infra.auth.types import (
    DeleteAuthApiResponse,
    DeleteAuthResult,
)
from app.tools.artifacts.auth.delete import delete_auths
from app.tools.artifacts.auth.get import get_auths
from app.tools.resources.names.get import get_names
from app.utils.cache.invalidate_tags import invalidate_tags


async def delete_auth_impl(
    pool: asyncpg.Pool,
    redis: Redis,
    *,
    profile_id: UUID,
    auth_ids: list[UUID],
    session_id: UUID | None = None,
) -> DeleteAuthApiResponse:
    """Auth bulk delete using composable infra functions.

    Flow:
      1. resolve_profile_identity_context -> role
      2. Per-item: resolve_auth_permissions_context -> exists, departments
      3. Per-item: inline SQL for active_settings_count
      4. Per-item: compute_can_delete -> permission check (fail fast)
      5. Fetch names for result messages
      6. Single transaction: delete_auths -> bulk delete
      7. invalidate_tags
      8. Keycloak sync
    """

    # -- Step 1: Profile context ------------------------------------------------

    profile = await resolve_profile_identity_context(
        pool,
        profile_id,
        redis,
        session_id=session_id,
    )

    if profile is None:
        raise HTTPException(
            status_code=401,
            detail="Profile not found. Please sign in again.",
        )

    # -- Step 2+3: Per-item permission checks (fail fast) -----------------------

    for idx, auth_id in enumerate(auth_ids):
        async with pool.acquire() as conn:
            ctx = await resolve_auth_permissions_context(conn, auth_id)

        if not ctx.exists:
            raise HTTPException(
                status_code=404,
                detail=f"Item {idx}: Auth {auth_id} not found.",
            )

        # Active settings count via setting_auths_junction
        async with pool.acquire() as conn:
            active_settings_count: int = await conn.fetchval(
                "SELECT COUNT(*)::int FROM setting_auths_junction WHERE auths_id = $1 AND active = true",
                auth_id,
            )

        if not compute_can_delete(
            user_role=profile.role,
            active_settings_count=active_settings_count or 0,
        ):
            raise HTTPException(
                status_code=403,
                detail=f"Item {idx}: You don't have permission to delete this auth entry.",
            )

    # -- Step 4: Fetch names for result messages --------------------------------

    name_map: dict[UUID, str] = {}
    async with pool.acquire() as conn:
        artifacts = await get_auths(conn, auth_ids, names=True)
    for artifact in artifacts:
        name = "Unknown"
        if artifact.name_ids:
            async with pool.acquire() as conn:
                name_resources = await get_names(conn, artifact.name_ids, redis)
            if name_resources:
                name = name_resources[0].name or "Unknown"
        name_map[artifact.id] = name

    # -- Step 5: Single transaction -- bulk delete ------------------------------

    async with pool.acquire() as conn:
        async with conn.transaction():
            result = await delete_auths(conn, auth_ids)

    # -- Step 6: Invalidate cache -----------------------------------------------

    await invalidate_tags(["auth"], redis=redis)

    # -- Step 7: Keycloak sync --------------------------------------------------

    try:
        from app.infra.identity.keycloak_sync import perform_keycloak_sync

        await perform_keycloak_sync(department_id=None)
    except Exception:
        pass  # Non-fatal

    results = [
        DeleteAuthResult(
            success=True,
            auth_id=pid,
            message=f"Auth '{name_map.get(pid, 'Unknown')}' deleted successfully",
        )
        for pid in result.deleted_ids
    ]

    return DeleteAuthApiResponse(results=results)
