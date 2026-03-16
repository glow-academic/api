"""Model delete logic — composable infra architecture.

Core delete function that composes existing black-box tools:
  1. resolve_profile_identity_context — profile (role)
  2. resolve_model_permissions_context — per-item exists, departments, usage
  3. compute_can_delete — permission check
  4. delete_models — bulk delete tool
  5. invalidate_tags — cache invalidation
"""

from __future__ import annotations

from uuid import UUID

import asyncpg
from fastapi import HTTPException
from redis.asyncio import Redis

from app.infra.model.permissions import compute_can_delete
from app.infra.model.permissions_context import resolve_model_permissions_context
from app.infra.profile_identity_context import resolve_profile_identity_context
from app.infra.model.types import (
    DeleteModelApiResponse,
    DeleteModelResult,
)
from app.tools.artifacts.model.delete import delete_models
from app.tools.artifacts.model.get import get_models
from app.tools.resources.names.get import get_names
from app.utils.cache.invalidate_tags import invalidate_tags


async def delete_model_impl(
    pool: asyncpg.Pool,
    redis: Redis,
    *,
    profile_id: UUID,
    model_ids: list[UUID],
    session_id: UUID | None = None,
) -> DeleteModelApiResponse:
    """Model bulk delete using composable infra functions.

    Flow:
      1. resolve_profile_identity_context -> role
      2. Per-item: resolve_model_permissions_context -> exists, departments, usage
      3. Per-item: compute_can_delete -> permission check (fail fast)
      4. Fetch names for result messages
      5. Single transaction: delete_models -> bulk delete
      6. invalidate_tags
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

    # -- Step 2+3: Per-item permission checks (fail fast) ----------------------

    async with pool.acquire() as conn:
        for idx, model_id in enumerate(model_ids):
            ctx = await resolve_model_permissions_context(conn, model_id)

            if not ctx.exists:
                raise HTTPException(
                    status_code=404,
                    detail=f"Item {idx}: Model {model_id} not found.",
                )

            if not compute_can_delete(
                user_role=profile.role,
                model_department_ids=ctx.department_ids,
                active_agent_count=ctx.active_agent_count,
            ):
                raise HTTPException(
                    status_code=403,
                    detail=f"Item {idx}: You don't have permission to delete this model.",
                )

    # -- Step 4: Fetch names for result messages -------------------------------

    async with pool.acquire() as conn:
        name_map: dict[UUID, str] = {}
        artifacts = await get_models(conn, model_ids, names=True)
        for artifact in artifacts:
            name = "Unknown"
            if artifact.name_ids:
                name_resources = await get_names(conn, artifact.name_ids, redis)
                if name_resources:
                    name = name_resources[0].name or "Unknown"
            name_map[artifact.id] = name

    # -- Step 5: Single transaction -- bulk delete -----------------------------

    async with pool.acquire() as conn:
        async with conn.transaction():
            result = await delete_models(conn, model_ids)

    # -- Step 6: Invalidate cache ----------------------------------------------

    await invalidate_tags(["models"], redis=redis)

    results = [
        DeleteModelResult(
            success=True,
            model_id=pid,
            message=f"Model '{name_map.get(pid, 'Unknown')}' deleted successfully",
        )
        for pid in result.deleted_ids
    ]

    return DeleteModelApiResponse(results=results)
