"""Profile delete logic — composable infra architecture.

Core delete function that composes existing black-box tools:
  1. resolve_profile_identity_context — current user's profile (role)
  2. resolve_profile_permissions_context — per-item exists check
  3. resolve_profile_identity_context (target) — target profile's role
  4. compute_can_delete — permission check (target_is_self, target_role)
  5. delete_profiles — bulk delete tool
  6. invalidate_tags — cache invalidation
"""

from __future__ import annotations

from uuid import UUID

import asyncpg
from fastapi import HTTPException
from redis.asyncio import Redis

from app.infra.profile.permissions import compute_can_delete
from app.infra.profile.permissions_context import resolve_profile_permissions_context
from app.infra.profile_identity_context import resolve_profile_identity_context
from app.infra.profile.types import (
    DeleteProfileApiResponse,
    DeleteProfileResult,
)
from app.tools.artifacts.profile.delete import delete_profiles
from app.tools.artifacts.profile.get import get_profiles
from app.tools.resources.names.get import get_names
from app.utils.cache.invalidate_tags import invalidate_tags


async def delete_profile_impl(
    pool: asyncpg.Pool,
    redis: Redis,
    *,
    profile_id: UUID,
    profile_ids: list[UUID],
    session_id: UUID | None = None,
) -> DeleteProfileApiResponse:
    """Profile bulk delete using composable infra functions.

    Flow:
      1. resolve_profile_identity_context -> current user's role
      2. Per-item: resolve_profile_permissions_context -> exists check
      3. Per-item: resolve_profile_identity_context (target) -> target role
      4. Per-item: compute_can_delete -> permission check (fail fast)
      5. Fetch names for result messages
      6. Single transaction: delete_profiles -> bulk delete
      7. invalidate_tags
    """

    # -- Step 1: Current user's profile context -----------------------------------

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

    # -- Step 2+3+4: Per-item permission checks (fail fast) -----------------------

    async with pool.acquire() as conn:
        for idx, target_id in enumerate(profile_ids):
            ctx = await resolve_profile_permissions_context(conn, target_id)

            if not ctx.exists:
                raise HTTPException(
                    status_code=404,
                    detail=f"Item {idx}: Profile {target_id} not found.",
                )

            # Resolve target's role
            target_ctx = await resolve_profile_identity_context(pool, target_id, redis)
            target_role = target_ctx.role if target_ctx else None

            if not compute_can_delete(
                user_role=profile.role,
                target_is_self=(target_id == profile_id),
                target_role=target_role,
            ):
                raise HTTPException(
                    status_code=403,
                    detail=f"Item {idx}: You don't have permission to delete this profile.",
                )

    # -- Step 5: Fetch names for result messages ----------------------------------

    async with pool.acquire() as conn:
        name_map: dict[UUID, str] = {}
        artifacts = await get_profiles(conn, profile_ids, names=True)
        for artifact in artifacts:
            name = "Unknown"
            if artifact.name_ids:
                name_resources = await get_names(conn, artifact.name_ids, redis)
                if name_resources:
                    name = name_resources[0].name or "Unknown"
            name_map[artifact.id] = name

    # -- Step 6: Single transaction — bulk delete ---------------------------------

    async with pool.acquire() as conn:
        async with conn.transaction():
            result = await delete_profiles(conn, profile_ids)

    # -- Step 7: Invalidate cache -------------------------------------------------

    await invalidate_tags(["profile"], redis=redis)

    results = [
        DeleteProfileResult(
            success=True,
            profile_id=pid,
            message=f"Profile '{name_map.get(pid, 'Unknown')}' deleted successfully",
        )
        for pid in result.deleted_ids
    ]

    return DeleteProfileApiResponse(results=results)
