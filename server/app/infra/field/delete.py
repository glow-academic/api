"""Field delete logic — composable infra architecture.

Core delete function that composes existing black-box tools:
  1. resolve_profile_identity_context — profile (role)
  2. resolve_field_permissions_context — per-item exists, departments
  3. search_parameters — inline usage check (active_parameter_count)
  4. compute_can_delete — permission check
  5. delete_fields — bulk delete tool
  6. invalidate_tags — cache invalidation
"""

from __future__ import annotations

from uuid import UUID

import asyncpg
from fastapi import HTTPException
from redis.asyncio import Redis

from app.infra.field.permissions import compute_can_delete
from app.infra.field.permissions_context import resolve_field_permissions_context
from app.infra.profile_identity_context import resolve_profile_identity_context
from app.infra.field.types import (
    DeleteFieldApiResponse,
    DeleteFieldResult,
)
from app.tools.artifacts.field.delete import delete_fields
from app.tools.artifacts.field.get import get_fields
from app.tools.artifacts.parameter.search import search_parameters
from app.tools.resources.names.get import get_names
from app.utils.cache.invalidate_tags import invalidate_tags


async def delete_field_impl(
    pool: asyncpg.Pool,
    redis: Redis,
    *,
    profile_id: UUID,
    field_ids: list[UUID],
    session_id: UUID | None = None,
) -> DeleteFieldApiResponse:
    """Field bulk delete using composable infra functions.

    Flow:
      1. resolve_profile_identity_context -> role
      2. Per-item: resolve_field_permissions_context -> exists, departments
      3. Per-item: search_parameters -> active_parameter_count (inline usage check)
      4. Per-item: compute_can_delete -> permission check (fail fast)
      5. Fetch names for result messages
      6. Single transaction: delete_fields -> bulk delete
      7. invalidate_tags
    """

    # -- Step 1: Profile context -----------------------------------------------

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

    # -- Step 2+3+4: Per-item permission checks (fail fast) --------------------

    async with pool.acquire() as conn:
        for idx, field_id in enumerate(field_ids):
            ctx = await resolve_field_permissions_context(conn, field_id)

            if not ctx.exists:
                raise HTTPException(
                    status_code=404,
                    detail=f"Item {idx}: Field {field_id} not found.",
                )

            # Field permissions context doesn't include active_parameter_count,
            # so we use search_parameters inline to check usage.
            active_parameter_ids, _total = await search_parameters(
                conn, field_ids=[field_id], active_only=True, limit_count=1
            )
            active_parameter_count = len(active_parameter_ids)

            if not compute_can_delete(
                user_role=profile.role,
                field_department_ids=ctx.department_ids,
                active_parameter_count=active_parameter_count,
            ):
                raise HTTPException(
                    status_code=403,
                    detail=f"Item {idx}: You don't have permission to delete this field.",
                )

    # -- Step 5: Fetch names for result messages -------------------------------

    async with pool.acquire() as conn:
        name_map: dict[UUID, str] = {}
        artifacts = await get_fields(conn, field_ids, names=True)
        for artifact in artifacts:
            name = "Unknown"
            if artifact.name_ids:
                name_resources = await get_names(conn, artifact.name_ids, redis)
                if name_resources:
                    name = name_resources[0].name or "Unknown"
            name_map[artifact.id] = name

    # -- Step 6: Single transaction -- bulk delete -----------------------------

    async with pool.acquire() as conn:
        async with conn.transaction():
            result = await delete_fields(conn, field_ids)

    # -- Step 7: Invalidate cache ----------------------------------------------

    await invalidate_tags(["fields"], redis=redis)

    results = [
        DeleteFieldResult(
            success=True,
            field_id=pid,
            message=f"Field '{name_map.get(pid, 'Unknown')}' deleted successfully",
        )
        for pid in result.deleted_ids
    ]

    return DeleteFieldApiResponse(results=results)
