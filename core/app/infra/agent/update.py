"""Agent update logic — composable infra architecture.

Composes existing black-box tools:
  1. resolve_profile_identity_context — profile (role, departments)
  2. resolve_agent_permissions_context — per-item access + edit check
  3. resolve_agent_values — raw value → ID resolution
  4. update_agent_artifact — junction writes (partial update)
  5. create_denormalized_snapshot — agents_resource snapshot
"""

from __future__ import annotations

from uuid import UUID

import asyncpg
from fastapi import HTTPException
from redis.asyncio import Redis

from app.infra.agent.permissions_context import (
    create_denormalized_snapshot,
    resolve_agent_permissions_context,
    resolve_agent_values,
)
from app.infra.profile_identity_context import resolve_profile_identity_context
from app.infra.agent.refresh import refresh_agent_impl
from app.tools.artifacts.agent.update import (
    _UNSET,
)
from app.tools.artifacts.agent.update import (
    update_agent as update_agent_artifact,
)
from app.infra.agent.types import UpdateAgentApiRequest, UpdateAgentApiResponse


async def update_agent_impl(
    pool: asyncpg.Pool,
    redis: Redis,
    *,
    profile_id: UUID,
    request: UpdateAgentApiRequest,
    session_id: UUID | None = None,
    draft_id: UUID | None = None,
    group_id: UUID | None = None,
    soft: bool = False,
    accept: bool | None = None,
    idempotency_key: UUID | None = None,
) -> UpdateAgentApiResponse:
    """Agent bulk update using composable infra functions.

    Flow:
      1. resolve_profile_identity_context → role, department_ids
      2. Per-item: resolve_agent_permissions_context → exists + compute_can_edit
      3. Per-item value resolution (raw → ID, no required field enforcement)
      4. Single transaction: update_agent_artifact + denormalized snapshot per item
      5. invalidate_tags
    """
    from app.infra.agent.permissions import (
        compute_can_edit,
        has_access,
    )
    from app.infra.agent.types import (
        AgentResultItem,
    )

    idempotency_key = idempotency_key or request.idempotency_key
    if idempotency_key and accept is None:
        accept = request.accept

    items = request.agents

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
            perms = await resolve_agent_permissions_context(conn, item.id)
            if not perms.exists:
                raise HTTPException(
                    status_code=404,
                    detail=f"Item {idx}: Agent {item.id} not found.",
                )
            has_agent_access = has_access(
                profile.role_level, profile.department_ids, perms.department_ids
            )
            if not compute_can_edit(
                role_level=profile.role_level, role_permissions=profile.role_permissions,
                has_agent_access=has_agent_access,
                missing_tools=[],
                agent_id=item.id,
            ):
                raise HTTPException(
                    status_code=403,
                    detail=f"Item {idx}: You don't have permission to update this agent.",
                )

    if accept is not None and idempotency_key is not None:
        if not accept:
            return UpdateAgentApiResponse(
                results=[
                    AgentResultItem(
                        success=True,
                        agent_id=item.id,
                        message="Update rejected",
                    )
                    for item in items
                ],
                idempotency_key=idempotency_key,
            )
        soft = False

    # ── Step 3: Per-item value resolution ──────────────────────────────

    has_errors = False
    error_results: list[AgentResultItem] = []

    async with pool.acquire() as conn:
        for idx, item in enumerate(items):
            item_errors = await resolve_agent_values(conn, redis, item, is_create=False)
            if item_errors:
                has_errors = True
                error_results.append(
                    AgentResultItem(
                        success=False,
                        message=f"Item {idx}: Validation errors",
                        errors=item_errors,
                    )
                )
            else:
                error_results.append(AgentResultItem(success=True, message="Validated"))

    if has_errors:
        return UpdateAgentApiResponse(
            results=error_results,
            idempotency_key=idempotency_key,
        )

    # ── Step 4: Single transaction ─────────────────────────────────────

    results: list[AgentResultItem] = []

    for item in items:
        agents_resource_id = None
        if not soft:
            agents_resource_id = await create_denormalized_snapshot(
                pool,
                redis,
                name_id=item.name_id,
                description_id=item.description_id,
                department_ids=item.department_ids,
                model_id=item.model_id,
                tool_ids=item.tool_ids,
                voice_ids=item.voice_ids,
            )

        # Artifact update inside transaction
        async with pool.acquire() as conn:
            async with conn.transaction():
                # Combine existing flag_ids with active_flag_id
                combined_flag_ids = list(item.flag_ids or [])
                if item.active_flag_id:
                    combined_flag_ids.append(item.active_flag_id)

                await update_agent_artifact(
                    conn,
                    item.id,
                    name_id=item.name_id if item.name_id else _UNSET,
                    description_id=item.description_id
                    if item.description_id
                    else _UNSET,
                    department_ids=item.department_ids,
                    flag_ids=combined_flag_ids or None,
                    model_ids=[item.model_id] if item.model_id else None,
                    reasoning_level_ids=item.reasoning_level_ids,
                    temperature_level_ids=item.temperature_level_ids,
                    tool_ids=item.tool_ids,
                    voice_ids=item.voice_ids,
                    agent_ids=[agents_resource_id],
                    soft=soft,
                )

        results.append(
            AgentResultItem(
                success=True,
                agent_id=item.id,
                message=(
                    "Agent update accepted"
                    if accept is not None and idempotency_key is not None
                    else "Agent updated (pending acceptance)"
                    if soft
                    else "Agent updated successfully"
                ),
            )
        )

    if not soft:
        await refresh_agent_impl(
            pool,
            redis,
            profile_id=profile_id,
            session_id=session_id,
            soft=soft,
            operation_key=idempotency_key or (results[0].agent_id if results else None),
        )

    return UpdateAgentApiResponse(
        results=results,
        idempotency_key=idempotency_key,
    )
