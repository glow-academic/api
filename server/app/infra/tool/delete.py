"""Tool delete logic — composable infra architecture.

Core delete function that composes existing black-box tools:
  1. resolve_profile_identity_context — profile (role)
  2. resolve_tool_permissions_context — per-item exists, usage
  3. compute_can_delete — permission check
  4. delete_tools — bulk delete tool
  5. invalidate_tags — cache invalidation
"""

from __future__ import annotations

from uuid import UUID

import asyncpg
from fastapi import HTTPException
from redis.asyncio import Redis

from app.infra.profile_identity_context import resolve_profile_identity_context
from app.infra.tool.permissions import compute_can_delete
from app.infra.tool.permissions_context import resolve_tool_permissions_context
from app.infra.tool.types import (
    DeleteToolApiResponse,
    DeleteToolResult,
)
from app.tools.artifacts.tool.delete import delete_tools
from app.tools.artifacts.tool.get import get_tools
from app.tools.resources.names.get import get_names
from app.utils.cache.invalidate_tags import invalidate_tags


async def delete_tool_impl(
    pool: asyncpg.Pool,
    redis: Redis,
    *,
    profile_id: UUID,
    tool_ids: list[UUID],
    session_id: UUID | None = None,
) -> DeleteToolApiResponse:
    """Tool bulk delete using composable infra functions.

    Flow:
      1. resolve_profile_identity_context -> role
      2. Per-item: resolve_tool_permissions_context -> exists, usage
      3. Per-item: compute_can_delete -> permission check (fail fast)
      4. Fetch names for result messages
      5. Single transaction: delete_tools -> bulk delete
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
        for idx, tool_id in enumerate(tool_ids):
            ctx = await resolve_tool_permissions_context(conn, tool_id)

            if not ctx.exists:
                raise HTTPException(
                    status_code=404,
                    detail=f"Item {idx}: Tool {tool_id} not found.",
                )

            if not compute_can_delete(
                user_role=profile.role,
                active_agent_count=ctx.active_agent_count,
            ):
                raise HTTPException(
                    status_code=403,
                    detail=f"Item {idx}: You don't have permission to delete this tool.",
                )

    # -- Step 4: Fetch names for result messages -------------------------------

    async with pool.acquire() as conn:
        name_map: dict[UUID, str] = {}
        artifacts = await get_tools(conn, tool_ids, names=True)
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
            result = await delete_tools(conn, tool_ids)

    # -- Step 6: Invalidate cache ----------------------------------------------

    await invalidate_tags(["tools"], redis=redis)

    results = [
        DeleteToolResult(
            success=True,
            tool_id=pid,
            message=f"Tool '{name_map.get(pid, 'Unknown')}' deleted successfully",
        )
        for pid in result.deleted_ids
    ]

    return DeleteToolApiResponse(results=results)
