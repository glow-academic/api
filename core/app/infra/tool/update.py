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
from app.infra.tool.refresh import refresh_tool_impl
from app.tools.artifacts.tool.update import (
    _UNSET,
)
from app.tools.artifacts.tool.update import (
    update_tool as update_tool_artifact,
)
from app.infra.tool.types import (
    UpdateToolApiRequest,
    UpdateToolApiResponse,
)


async def update_tool_impl(
    pool: asyncpg.Pool,
    redis: Redis,
    *,
    profile_id: UUID,
    request: UpdateToolApiRequest,
    session_id: UUID | None = None,
    draft_id: UUID | None = None,
    group_id: UUID | None = None,
    soft: bool = False,
    accept: bool | None = None,
    idempotency_key: UUID | None = None,
) -> UpdateToolApiResponse:
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
    )

    idempotency_key = idempotency_key or request.idempotency_key
    if idempotency_key and accept is None:
        accept = request.accept

    items = request.tools

    # ── Step 1: Profile context ────────────────────────────────────────

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

    # ── Step 2: Per-item permission check ──────────────────────────────

    async with pool.acquire() as conn:
        for idx, item in enumerate(items):
            perms = await resolve_tool_permissions_context(conn, item.id)
            if not perms.exists:
                raise HTTPException(
                    status_code=404,
                    detail=f"Item {idx}: Tool {item.id} not found.",
                )
            if not compute_can_edit(
                role_level=profile.role_level, role_permissions=profile.role_permissions,
                active_agent_count=perms.active_agent_count,
            ):
                raise HTTPException(
                    status_code=403,
                    detail=f"Item {idx}: You don't have permission to update this tool.",
                )

    # ── Short-circuit: ack path ───────────────────────────────────────
    if accept is not None and idempotency_key is not None:
        if not accept:
            return UpdateToolApiResponse(
                results=[
                    ToolResultItem(
                        success=True,
                        tool_id=item.id,
                        message="Update rejected",
                    )
                    for item in items
                ],
                idempotency_key=idempotency_key,
            )

        soft = False

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
        return UpdateToolApiResponse(results=error_results, idempotency_key=idempotency_key)

    # ── Step 4: Single transaction ─────────────────────────────────────

    results: list[ToolResultItem] = []

    for item in items:
        # Create denormalized snapshot OUTSIDE transaction (skip when soft).
        tools_resource_id = None
        if not soft:
            tools_resource_id = await create_denormalized_snapshot(
                pool,
                redis,
                name_id=item.name_id,
                description_id=item.description_id,
                department_ids=item.department_ids,
                args_ids=item.args_ids,
                args_output_ids=item.args_outputs_ids,
                permission_ids=item.permission_ids,
            )

        # Combine active_flag_id with any other flag_ids
        combined_flag_ids = list(item.flag_ids or [])
        if item.active_flag_id:
            combined_flag_ids.append(item.active_flag_id)

        # Artifact update inside transaction
        async with pool.acquire() as conn:
            async with conn.transaction():
                await update_tool_artifact(
                    conn,
                    item.id,
                    name_id=item.name_id if item.name_id else _UNSET,
                    description_id=item.description_id
                    if item.description_id
                    else _UNSET,
                    department_ids=item.department_ids,
                    flag_ids=combined_flag_ids or None,
                    arg_positions_ids=item.arg_positions_ids,
                    args_ids=item.args_ids,
                    args_outputs_ids=item.args_outputs_ids,
                    permission_ids=item.permission_ids,
                    tool_ids=[tools_resource_id] if tools_resource_id else None,
                    soft=soft,
                )

        results.append(
            ToolResultItem(
                success=True,
                tool_id=item.id,
                message=(
                    "Tool update accepted"
                    if accept is not None and idempotency_key is not None
                    else "Tool updated (pending acceptance)"
                    if soft
                    else "Tool updated successfully"
                ),
            )
        )

    # ── Step 5: Refresh via canonical helper ────────────────────────────

    if not soft:
        await refresh_tool_impl(
            pool,
            redis,
            profile_id=profile_id,
            session_id=session_id,
            soft=soft,
            operation_key=idempotency_key or (results[0].tool_id if results else None),
        )

    return UpdateToolApiResponse(
        results=results,
        idempotency_key=idempotency_key,
    )
