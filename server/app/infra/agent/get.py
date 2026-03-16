"""Canonical shared agent GET operation."""

from __future__ import annotations

from uuid import UUID

import asyncpg
from fastapi import HTTPException
from redis.asyncio import Redis

from app.infra.agent.context import resolve_agent_context
from app.infra.agent.permissions import AGENT_RESOURCES, has_access
from app.infra.agent.permissions_context import resolve_agent_permissions_context
from app.infra.agent.sections import build_agent_get_result
from app.infra.common_context import resolve_common_context
from app.infra.tool_graph import score_tools
from app.infra.agent.types import GetAgentApiResponse


async def get_agent_impl(
    pool: asyncpg.Pool,
    redis: Redis,
    *,
    profile_id: UUID,
    session_id: UUID | None = None,
    agent_id: UUID | None,
    draft_id: UUID | None = None,
    group_id: UUID | None = None,
    bypass_cache: bool = False,
) -> GetAgentApiResponse:
    """Resolve the canonical agent artifact bundle for any surface."""
    common = await resolve_common_context(
        pool,
        redis,
        profile_id=profile_id,
        session_id=session_id,
        group_id=group_id,
        draft_id=draft_id,
        artifact_type="agent",
        bypass_cache=bypass_cache,
    )
    if common is None:
        raise HTTPException(
            status_code=401,
            detail="Profile not found. Please sign in again.",
        )

    effective_group_id = group_id or common.profile.group_id

    perms = None
    if agent_id is not None:
        async with pool.acquire() as conn:
            perms = await resolve_agent_permissions_context(conn, agent_id)
        if not perms.exists:
            raise HTTPException(
                status_code=404,
                detail=f"Agent {agent_id} not found",
            )
        if not has_access(
            common.profile.role,
            common.profile.department_ids,
            perms.department_ids,
        ):
            raise HTTPException(
                status_code=403,
                detail="You don't have access to this agent. It may be restricted to other departments.",
            )

    agent_ctx = await resolve_agent_context(
        pool,
        redis,
        agent_id=agent_id,
        group_id=effective_group_id,
        draft_id=draft_id,
        user_department_ids=common.profile.department_ids,
        bypass_cache=bypass_cache,
    )

    scores = score_tools(common.tool_graph, AGENT_RESOURCES)

    return build_agent_get_result(
        common=common,
        agent_ctx=agent_ctx,
        scores=scores,
        perms=perms,
        agent_id=agent_id,
        group_id=effective_group_id,
    )
