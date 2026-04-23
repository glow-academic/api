"""Agent delete logic — composable infra architecture.

Core delete function that composes existing black-box tools:
  1. resolve_profile_identity_context — profile (role)
  2. Per-item loop: permissions context + inline SQL for active_settings_count
  3. compute_can_delete — permission check
  4. delete_agents — bulk delete tool
  5. invalidate_tags — cache invalidation
"""

from __future__ import annotations

from uuid import UUID

import asyncpg
from fastapi import HTTPException
from redis.asyncio import Redis

from app.infra.delete.delete_artifact import restore_artifacts
from app.infra.agent.permissions import compute_can_delete
from app.infra.agent.permissions_context import resolve_agent_permissions_context
from app.infra.profile_identity_context import resolve_profile_identity_context
from app.infra.agent.refresh import refresh_agent_impl
from app.infra.agent.types import (
    DeleteAgentApiResponse,
    DeleteAgentResult,
)
from app.tools.artifacts.agent.delete import delete_agents
from app.tools.artifacts.agent.get import get_agents
from app.tools.resources.names.get import get_names


async def delete_agent_impl(
    pool: asyncpg.Pool,
    redis: Redis,
    *,
    profile_id: UUID,
    ids: list[UUID],
    session_id: UUID | None = None,
    soft: bool = False,
    accept: bool | None = None,
    idempotency_key: UUID | None = None,
) -> DeleteAgentApiResponse:
    """Agent bulk delete using composable infra functions.

    Flow:
      1. resolve_profile_identity_context -> role
      2. Per-item: resolve_agent_permissions_context -> exists, departments
      3. Per-item: inline SQL for active_settings_count
      4. Per-item: compute_can_delete -> permission check (fail fast)
      5. Fetch names for result messages
      6. Single transaction: delete_agents -> bulk delete
      7. invalidate_tags
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

    async with pool.acquire() as conn:
        for idx, agent_id in enumerate(ids):
            ctx = await resolve_agent_permissions_context(conn, agent_id)

            if not ctx.exists:
                raise HTTPException(
                    status_code=404,
                    detail=f"Item {idx}: Agent {agent_id} not found.",
                )

            # Active settings count via runs_agents_connection through agent_agents_junction
            active_settings_count: int = await conn.fetchval(
                """
                SELECT COUNT(DISTINCT rac.run_id)::int
                FROM agent_agents_junction aaj
                JOIN runs_agents_connection rac ON rac.agents_id = aaj.agents_id AND rac.active = true
                WHERE aaj.agent_id = $1 AND aaj.active = true
                """,
                agent_id,
            )

            if not compute_can_delete(
                role_level=profile.role_level, role_permissions=profile.role_permissions,
                active_settings_count=active_settings_count or 0,
            ):
                raise HTTPException(
                    status_code=403,
                    detail=f"Item {idx}: You don't have permission to delete this agent.",
                )

    if accept is not None and idempotency_key is not None:
        if not accept:
            async with pool.acquire() as conn:
                async with conn.transaction():
                    await restore_artifacts(
                        conn,
                        table="agent_artifact",
                        ids=ids,
                    )
        await refresh_agent_impl(
            pool,
            redis,
            profile_id=profile_id,
            session_id=session_id,
            operation_key=idempotency_key,
        )
        return DeleteAgentApiResponse(
            results=[
                DeleteAgentResult(
                    success=True,
                    agent_id=agent_id,
                    message="Delete confirmed" if accept else "Delete rejected — agent restored",
                )
                for agent_id in ids
            ],
            idempotency_key=idempotency_key,
        )

    # -- Step 4: Fetch names for result messages --------------------------------

    async with pool.acquire() as conn:
        name_map: dict[UUID, str] = {}
        artifacts = await get_agents(conn, ids, names=True)
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
            result = await delete_agents(conn, ids, soft=soft)

    await refresh_agent_impl(
        pool,
        redis,
        profile_id=profile_id,
        session_id=session_id,
        soft=soft,
        operation_key=idempotency_key or (result.deleted_ids[0] if result.deleted_ids else None),
    )

    results = [
        DeleteAgentResult(
            success=True,
            agent_id=pid,
            message=(
                f"Agent '{name_map.get(pid, 'Unknown')}' deleted (pending confirmation)"
                if soft
                else f"Agent '{name_map.get(pid, 'Unknown')}' deleted successfully"
            ),
        )
        for pid in result.deleted_ids
    ]

    return DeleteAgentApiResponse(
        results=results,
        idempotency_key=idempotency_key,
    )
