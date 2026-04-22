"""Load an agent's system prompt text from its resource snapshot.

mcp_resource.agent_id references an agents_resource (denormalized
snapshot). The snapshot carries prompt_id directly — no artifact walk.
"""

from __future__ import annotations

from uuid import UUID

import asyncpg
from redis.asyncio import Redis

from app.tools.resources.agents.get import get_agents as get_agent_resources
from app.tools.resources.prompts.get import get_prompts


async def get_agent_system_prompt(
    pool: asyncpg.Pool,
    redis: Redis,
    agent_resource_id: UUID,
    bypass_cache: bool = False,
) -> str | None:
    """Return the rendered system_prompt text for the agent, or None."""
    async with pool.acquire() as conn:
        resources = await get_agent_resources(
            conn, [agent_resource_id], redis, bypass_cache
        )
    if not resources or not resources[0].prompt_id:
        return None

    async with pool.acquire() as conn:
        prompts = await get_prompts(conn, [resources[0].prompt_id], redis, bypass_cache)
    if not prompts:
        return None
    return prompts[0].system_prompt or None
