"""Department delete logic — composable infra architecture.

Core delete function that composes existing black-box tools:
  1. resolve_profile_identity_context — profile (role)
  2. Per-item loop: resolve_department_permissions_context -> exists, usage_count
  3. compute_can_delete — permission check
  4. delete_departments — bulk delete tool
  5. invalidate_tags — cache invalidation
  6. Keycloak sync — post-delete per department
"""

from __future__ import annotations

from uuid import UUID

import asyncpg
from fastapi import HTTPException
from redis.asyncio import Redis

from app.infra.department.permissions import compute_can_delete
from app.infra.department.permissions_context import (
    resolve_department_permissions_context,
)
from app.infra.profile_identity_context import resolve_profile_identity_context
from app.infra.department.types import (
    DeleteDepartmentApiResponse,
    DeleteDepartmentResult,
)
from app.tools.artifacts.department.delete import delete_departments
from app.tools.artifacts.department.get import get_departments
from app.tools.resources.names.get import get_names
from app.utils.cache.invalidate_tags import invalidate_tags


async def delete_department_impl(
    pool: asyncpg.Pool,
    redis: Redis,
    *,
    profile_id: UUID,
    department_ids: list[UUID],
    session_id: UUID | None = None,
) -> DeleteDepartmentApiResponse:
    """Department bulk delete using composable infra functions.

    Flow:
      1. resolve_profile_identity_context -> role
      2. Per-item: resolve_department_permissions_context -> exists, usage_count
      3. Per-item: compute_can_delete -> permission check (fail fast)
      4. Fetch names for result messages
      5. Single transaction: delete_departments -> bulk delete
      6. invalidate_tags
      7. Keycloak sync per department
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

    for idx, department_id in enumerate(department_ids):
        async with pool.acquire() as conn:
            ctx = await resolve_department_permissions_context(conn, department_id)

        if not ctx.exists:
            raise HTTPException(
                status_code=404,
                detail=f"Item {idx}: Department {department_id} not found.",
            )

        if not compute_can_delete(
            user_role=profile.role,
            total_usage=ctx.usage_count,
        ):
            raise HTTPException(
                status_code=403,
                detail=f"Item {idx}: You don't have permission to delete this department.",
            )

    # -- Step 4: Fetch names for result messages --------------------------------

    name_map: dict[UUID, str] = {}
    async with pool.acquire() as conn:
        artifacts = await get_departments(conn, department_ids, names=True)
        for artifact in artifacts:
            name = "Unknown"
            if artifact.name_ids:
                name_resources = await get_names(conn, artifact.name_ids, redis)
                if name_resources:
                    name = name_resources[0].name or "Unknown"
            name_map[artifact.id] = name

    # -- Step 5: Single transaction -- bulk delete ------------------------------

    async with pool.acquire() as conn:
        async with conn.transaction():
            result = await delete_departments(conn, department_ids)

    # -- Step 6: Invalidate cache -----------------------------------------------

    await invalidate_tags(["departments"], redis=redis)

    # -- Step 7: Keycloak sync per department -----------------------------------

    try:
        from app.infra.identity.keycloak_sync import perform_keycloak_sync

        for dept_id in result.deleted_ids:
            await perform_keycloak_sync(department_id=str(dept_id))
    except Exception:
        pass  # Non-fatal

    results = [
        DeleteDepartmentResult(
            success=True,
            department_id=pid,
            message=f"Department '{name_map.get(pid, 'Unknown')}' deleted successfully",
        )
        for pid in result.deleted_ids
    ]

    return DeleteDepartmentApiResponse(results=results)
