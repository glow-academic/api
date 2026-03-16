"""Tool update logic — composable infra architecture.

Composes existing black-box tools:
  1. resolve_profile_identity_context — profile (role)
  2. resolve_tool_permissions_context — per-item access + edit check
  3. resolve_tool_values — raw value → ID resolution
  4. update_tool_artifact — junction writes (partial update)
  5. create_denormalized_snapshot — tools_resource snapshot
"""

from __future__ import annotations

from uuid import UUID

import asyncpg
from fastapi import HTTPException
from redis.asyncio import Redis

from app.infra.profile_identity_context import resolve_profile_identity_context
from app.infra.tool.permissions_context import (
    create_denormalized_snapshot,
    resolve_tool_permissions_context,
    resolve_tool_values,
)
from app.tools.artifacts.tool.update import (
    _UNSET,
)
from app.tools.artifacts.tool.update import (
    update_tool as update_tool_artifact,
)
from app.utils.cache.invalidate_tags import invalidate_tags


async def update_tool_impl(
    pool: asyncpg.Pool,
    redis: Redis,
    *,
    profile_id: UUID,
    items: list,
    session_id: UUID | None = None,
    draft_id: UUID | None = None,
    group_id: UUID | None = None,
) -> dict:
    """Tool bulk update using composable infra functions.

    Flow:
      1. resolve_profile_identity_context → role
      2. Per-item: resolve_tool_permissions_context → exists + compute_can_edit
      3. Per-item value resolution (raw → ID, no required field enforcement)
      4. Single transaction: update_tool_artifact + denormalized snapshot per item
      5. invalidate_tags
    """
    from app.infra.tool.permissions import compute_can_edit
    from app.infra.tool.types import (
        ToolResultItem,
        UpdateToolApiResponse,
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
            perms = await resolve_tool_permissions_context(conn, item.tool_id)
            if not perms.exists:
                raise HTTPException(
                    status_code=404,
                    detail=f"Item {idx}: Tool {item.tool_id} not found.",
                )
            if not compute_can_edit(
                user_role=profile.role,
                active_agent_count=perms.active_agent_count,
            ):
                raise HTTPException(
                    status_code=403,
                    detail=f"Item {idx}: You don't have permission to update this tool.",
                )

    # ── Step 3: Per-item value resolution ──────────────────────────────

    has_errors = False
    error_results: list[ToolResultItem] = []

    async with pool.acquire() as conn:
        for idx, item in enumerate(items):
            item_errors = await resolve_tool_values(conn, redis, item, is_create=False)
            if item_errors:
                has_errors = True
                error_results.append(
                    ToolResultItem(
                        success=False,
                        message=f"Item {idx}: Validation errors",
                        errors=item_errors,
                    )
                )
            else:
                error_results.append(ToolResultItem(success=True, message="Validated"))

    if has_errors:
        return UpdateToolApiResponse(results=error_results)

    # ── Step 4: Single transaction ─────────────────────────────────────

    results: list[ToolResultItem] = []

    for item in items:
        # Create denormalized snapshot OUTSIDE transaction (read-only hydration)
        tools_resource_id = await create_denormalized_snapshot(
            pool,
            redis,
            name_id=item.name_id,
            description_id=item.description_id,
            department_ids=item.department_ids,
            args_ids=item.args_ids,
            args_output_ids=item.args_outputs_ids,
            operation_ids=item.operation_ids,
            artifact_ids=item.artifact_ids,
        )

        # Artifact update inside transaction
        async with pool.acquire() as conn:
            async with conn.transaction():
                await update_tool_artifact(
                    conn,
                    item.tool_id,
                    name_id=item.name_id if item.name_id else _UNSET,
                    description_id=item.description_id
                    if item.description_id
                    else _UNSET,
                    department_ids=item.department_ids,
                    flag_ids=item.flag_ids,
                    arg_positions_ids=item.arg_positions_ids,
                    args_ids=item.args_ids,
                    args_outputs_ids=item.args_outputs_ids,
                    artifact_ids=item.artifact_ids,
                    operation_ids=item.operation_ids,
                    tool_ids=[tools_resource_id],
                )

        results.append(
            ToolResultItem(
                success=True,
                tool_id=item.tool_id,
                message="Tool updated successfully",
            )
        )

    # ── Step 5: Invalidate cache ───────────────────────────────────────

    await invalidate_tags(["tools"], redis=redis)

    return UpdateToolApiResponse(results=results)
