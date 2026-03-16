"""Agent duplicate logic — composable infra architecture.

Core duplicate function that composes existing black-box tools:
  1. resolve_profile_identity_context — profile (role)
  2. compute_can_duplicate — permission check
  3. get_agents — fetch original with all junction IDs
  4. create_name — new name resource ("{name} Copy")
  5. search_flags — find inactive flag (agent_active, value=false)
  6. create_agent — new artifact with original's IDs + new name + inactive flag
  7. invalidate_tags — cache invalidation
"""

from __future__ import annotations

from uuid import UUID

import asyncpg
from fastapi import HTTPException
from redis.asyncio import Redis

from app.infra.agent.permissions import compute_can_duplicate
from app.infra.profile_identity_context import resolve_profile_identity_context
from app.infra.agent.types import (
    DuplicateAgentApiResponse,
)
from app.tools.artifacts.agent.create import (
    create_agent as create_agent_artifact,
)
from app.tools.artifacts.agent.get import get_agents
from app.tools.resources.flags.search import search_flags
from app.tools.resources.names.create import create_name
from app.tools.resources.names.get import get_names
from app.utils.cache.invalidate_tags import invalidate_tags


async def duplicate_agent_impl(
    pool: asyncpg.Pool,
    redis: Redis,
    *,
    profile_id: UUID,
    agent_id: UUID,
    session_id: UUID | None = None,
) -> DuplicateAgentApiResponse:
    """Agent duplicate using composable infra functions.

    Flow:
      1. resolve_profile_identity_context -> role
      2. compute_can_duplicate -> permission check
      3. get_agents -> fetch original with all junctions
      4. create_name("{name} Copy") -> new name resource
      5. search_flags -> find inactive flag (agent_active, value=false)
      6. create_agent -> new artifact with original IDs + inactive flag
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

    # -- Step 2: Permission check -----------------------------------------------

    if not compute_can_duplicate(user_role=profile.role):
        raise HTTPException(
            status_code=403,
            detail="You don't have permission to duplicate this agent.",
        )

    # -- Step 3: Fetch original agent with all junctions ------------------------

    async with pool.acquire() as conn:
        originals = await get_agents(
            conn,
            [agent_id],
            names=True,
            descriptions=True,
            departments=True,
            models=True,
            reasoning_levels=True,
            temperature_levels=True,
            tools=True,
            voices=True,
            agents=True,
        )

    if not originals:
        raise HTTPException(
            status_code=404,
            detail=f"Agent {agent_id} not found.",
        )

    original = originals[0]

    # -- Step 4: Create new name resource ---------------------------------------

    async with pool.acquire() as conn:
        original_name = "Unknown"
        if original.name_ids:
            name_resources = await get_names(conn, original.name_ids, redis)
            if name_resources:
                original_name = name_resources[0].name or "Unknown"

        new_name_resource = await create_name(conn, f"{original_name} Copy", redis)

    # -- Step 5: Find inactive flag (agent_active, value=false) -----------------

    async with pool.acquire() as conn:
        inactive_flag_id: UUID | None = None
        flag_results = await search_flags(
            conn,
            redis,
            flag_type="agent_active",
            agent=True,
            limit_count=10,
        )
        inactive_match = next((f for f in flag_results if not f.value), None)
        if inactive_match:
            inactive_flag_id = inactive_match.id

    # -- Step 6: Create new agent artifact with inactive flag -------------------

    flag_ids = [inactive_flag_id] if inactive_flag_id else None

    async with pool.acquire() as conn:
        async with conn.transaction():
            result = await create_agent_artifact(
                conn,
                name_id=new_name_resource.id,
                description_id=original.description_ids[0]
                if original.description_ids
                else None,
                department_ids=original.department_ids,
                model_ids=original.model_ids,
                reasoning_level_ids=original.reasoning_level_ids,
                temperature_level_ids=original.temperature_level_ids,
                tool_ids=original.tool_ids,
                voice_ids=original.voice_ids,
                agent_ids=original.agent_ids,
                flag_ids=flag_ids,
            )

    # -- Step 7: Invalidate cache -----------------------------------------------

    await invalidate_tags(["agents"], redis=redis)

    return DuplicateAgentApiResponse(
        success=True,
        agent_id=result.id,
        message=f"Agent '{original_name}' duplicated successfully",
    )
