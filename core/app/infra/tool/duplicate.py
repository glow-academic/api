"""Tool duplicate logic — composable infra architecture.

Core duplicate function that composes existing black-box tools:
  1. resolve_profile_identity_context — profile (role)
  2. compute_can_duplicate — permission check
  3. get_tools — fetch original with all junction IDs
  4. create_name — new name resource ("{name} Copy")
  5. search_flags — find inactive flag (tool_active, value=false)
  6. create_tool — new artifact with original's IDs + new name + inactive flag
  7. invalidate_tags — cache invalidation
"""

from __future__ import annotations

from uuid import UUID

import asyncpg
from fastapi import HTTPException
from redis.asyncio import Redis

from app.infra.profile_identity_context import resolve_profile_identity_context
from app.infra.tool.hydrate_list_rows import hydrate_tool_list_rows
from app.infra.tool.permissions import compute_can_duplicate
from app.infra.tool.refresh import refresh_tool_impl
from app.infra.tool.types import (
    DuplicateToolApiResponse,
)
from app.tools.artifacts.tool.create import (
    create_tool as create_tool_artifact,
)
from app.tools.artifacts.tool.get import get_tools
from app.tools.entries.soft_calls.create import create_soft_call
from app.tools.entries.soft_calls.get import get_soft_call
from app.tools.entries.soft_calls.refresh import refresh_soft_calls
from app.tools.resources.flags.search import search_flags
from app.tools.resources.names.create import create_name
from app.tools.resources.names.get import get_names

ARTIFACT = "tool"


async def duplicate_tool_impl(
    pool: asyncpg.Pool,
    redis: Redis,
    *,
    profile_id: UUID,
    id: UUID,
    session_id: UUID | None = None,
    soft: bool = False,
    accept: bool | None = None,
    idempotency_key: UUID | None = None,
) -> DuplicateToolApiResponse:
    """Tool duplicate using composable infra functions.

    Flow:
      1. resolve_profile_identity_context -> role
      2. compute_can_duplicate -> permission check
      3. get_tools -> fetch original with all junctions
      4. create_name("{name} Copy") -> new name resource
      5. search_flags -> find inactive flag (tool_active, value=false)
      6. create_tool -> new artifact with original IDs + inactive flag
      7. invalidate_tags
    """
    tool_id = id  # alias: tools send 'id', internal code uses 'tool_id'

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

    # -- Step 2: Permission check -----------------------------------------------

    if not compute_can_duplicate(role_level=profile.role_level, role_permissions=profile.role_permissions):
        raise HTTPException(
            status_code=403,
            detail="You don't have permission to duplicate this tool.",
        )

    # -- Step 3: Ack short-circuit ---------------------------------------------

    if accept is not None and idempotency_key is not None:
        async with pool.acquire() as conn:
            entry = await get_soft_call(conn, idempotency_key, artifact=ARTIFACT)
        if entry is None or entry.status != "pending" or entry.operation != "duplicate":
            raise HTTPException(
                status_code=404,
                detail="No pending tool duplicate for this call.",
            )
        target_id = entry.artifact_id

        if not accept:
            async with pool.acquire() as conn:
                await create_soft_call(
                    conn,
                    call_id=idempotency_key,
                    artifact=ARTIFACT,
                    operation="duplicate",
                    artifact_id=target_id,
                    status="rejected",
                )
            async with pool.acquire() as conn:
                await refresh_soft_calls(conn)
            return DuplicateToolApiResponse(
                success=True,
                tool_id=target_id,
                message="Tool duplicate rejected",
                idempotency_key=idempotency_key,
            )
        soft = False
        idempotency_key = target_id

    # -- Step 4: Fetch original tool with all junctions -------------------------

    async with pool.acquire() as conn:
        originals = await get_tools(
            conn,
            [tool_id],
            names=True,
            descriptions=True,
            departments=True,
            args=True,
            args_outputs=True,
            arg_positions=True,
            permissions=True,
            tools=True,
        )

    if not originals:
        raise HTTPException(
            status_code=404,
            detail=f"Tool {tool_id} not found.",
        )

    original = originals[0]

    # -- Step 5: Create new name resource ---------------------------------------

    async with pool.acquire() as conn:
        original_name = "Unknown"
        if original.name_ids:
            name_resources = await get_names(pool, original.name_ids, redis)
            if name_resources:
                original_name = name_resources[0].name or "Unknown"

        new_name_resource = await create_name(conn, f"{original_name} Copy", redis)

    # -- Step 6: Find inactive flag (tool_active, value=false) ------------------

    async with pool.acquire() as conn:
        inactive_flag_id: UUID | None = None
        flag_results = await search_flags(
            conn,
            redis,
            flag_type="tool_active",
            tool=True,
            limit_count=10,
        )
        inactive_match = next((f for f in flag_results if not f.value), None)
        if inactive_match:
            inactive_flag_id = inactive_match.id

    # -- Step 7: Create new tool artifact with inactive flag --------------------

    flag_ids = [inactive_flag_id] if inactive_flag_id else None

    async with pool.acquire() as conn:
        async with conn.transaction():
            result = await create_tool_artifact(
                conn,
                id=idempotency_key,
                name_id=new_name_resource.id,
                description_id=original.description_ids[0]
                if original.description_ids
                else None,
                department_ids=original.department_ids,
                arg_positions_ids=original.arg_positions_ids,
                args_ids=original.args_ids,
                args_outputs_ids=original.args_outputs_ids,
                permission_ids=original.permission_ids,
                tool_ids=original.tool_ids,
                flag_ids=flag_ids,
                soft=soft,
            )

            if soft and idempotency_key is not None:
                await create_soft_call(
                    conn,
                    call_id=idempotency_key,
                    artifact=ARTIFACT,
                    operation="duplicate",
                    artifact_id=result.id,
                )
            elif accept is True and idempotency_key is not None:
                await create_soft_call(
                    conn,
                    call_id=idempotency_key,
                    artifact=ARTIFACT,
                    operation="duplicate",
                    artifact_id=result.id,
                    status="accepted",
                )

    if (soft or accept is True) and idempotency_key is not None:
        async with pool.acquire() as conn:
            await refresh_soft_calls(conn)

    # -- Step 8: Refresh only when live write occurred --------------------------

    if not soft:
        await refresh_tool_impl(
            pool,
            redis,
            profile_id=profile_id,
            session_id=session_id,
            operation_key=idempotency_key or result.id,
        )

    # Hydrate the new row for the client's ghost rail. Skip on soft —
    # the dormant duplicate isn't visible until ack-accept promotes it.
    hydrated_tools: list | None = None
    if not soft and result.id is not None:
        hydrated_tools = await hydrate_tool_list_rows(
            pool, redis, profile_id=profile_id, tool_ids=[result.id],
        )

    return DuplicateToolApiResponse(
        success=True,
        tool_id=result.id,
        message=(
            "Tool duplicate accepted"
            if accept is not None and idempotency_key is not None
            else
            "Tool duplicated (pending acceptance)"
            if soft
            else f"Tool '{original_name}' duplicated successfully"
        ),
        idempotency_key=idempotency_key,
        tools=hydrated_tools,
    )
