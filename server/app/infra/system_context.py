"""Resolve system context — system → agents → models/providers/tools/args.

Given a system_id, fetches the system resource, then hydrates the full chain:
  system → agents → (models + tools) → (providers + args + args_outputs + prompts + instructions)

Composes existing black-box fetchers — no raw SQL.
"""

from __future__ import annotations

import asyncio
from dataclasses import dataclass
from uuid import UUID

import asyncpg
from redis.asyncio import Redis

from app.tools.resources.agents.get import get_agents
from app.tools.resources.args.get import get_args
from app.tools.resources.args_outputs.get import get_args_outputs
from app.tools.resources.instructions.get import get_instructions
from app.tools.resources.models.get import get_models
from app.tools.resources.prompts.get import get_prompts
from app.tools.resources.providers.get import get_providers
from app.tools.resources.rubrics.get import get_rubrics
from app.tools.resources.systems.get import get_systems
from app.tools.resources.tools.get import get_tools


@dataclass(frozen=True)
class SystemContext:
    """Fully hydrated system with agents, models, providers, tools, args, prompts, instructions."""

    system_id: UUID
    agents: list  # GetAgentResponse
    models: list  # GetModelResponse
    providers: list  # GetProviderResponse
    tools: list  # GetToolResponse
    args: list  # GetArgResponse
    args_outputs: list  # GetArgOutputResponse
    prompts: list  # GetPromptResponse
    instructions: list  # GetInstructionResponse
    rubrics: list  # GetRubricResponse


async def resolve_system_context(
    pool: asyncpg.Pool,
    redis: Redis,
    *,
    system_id: UUID,
    bypass_cache: bool = False,
) -> SystemContext | None:
    """Resolve a system into fully hydrated resources.

    Each parallel batch acquires its own connection from the pool.

    Steps:
      1. Fetch system → agent_ids
      2. Fetch agents → collect model_ids + tool_ids
      3. Parallel: models + tools + prompts + instructions + rubrics
      4. Parallel: providers + args + args_outputs
    """
    # Step 1: fetch system
    async with pool.acquire() as conn:
        systems = await get_systems(conn, [system_id], redis, bypass_cache)
    if not systems:
        return None

    system = systems[0]
    agent_ids = system.agent_ids or []

    if not agent_ids:
        return SystemContext(
            system_id=system_id,
            agents=[],
            models=[],
            providers=[],
            tools=[],
            args=[],
            args_outputs=[],
            prompts=[],
            instructions=[],
            rubrics=[],
        )

    # Step 2: fetch agents
    async with pool.acquire() as conn:
        agents = await get_agents(conn, agent_ids, redis, bypass_cache)

    # Collect IDs for next level
    model_ids = list({a.model_id for a in agents if a.model_id})
    tool_ids = list({tid for a in agents for tid in (a.tool_ids or [])})
    prompt_ids = list({a.prompt_id for a in agents if a.prompt_id})
    instruction_ids = list({iid for a in agents for iid in (a.instruction_ids or [])})
    rubric_ids = list({a.rubric_id for a in agents if a.rubric_id})

    # Step 3: parallel fetch models + tools + prompts + instructions + rubrics

    async def _get_models() -> list:
        if not model_ids:
            return []
        async with pool.acquire() as conn:
            return await get_models(conn, model_ids, redis, bypass_cache)

    async def _get_tools() -> list:
        if not tool_ids:
            return []
        async with pool.acquire() as conn:
            return await get_tools(conn, tool_ids, redis, bypass_cache)

    async def _get_prompts() -> list:
        if not prompt_ids:
            return []
        async with pool.acquire() as conn:
            return await get_prompts(conn, prompt_ids, redis, bypass_cache)

    async def _get_instructions() -> list:
        if not instruction_ids:
            return []
        async with pool.acquire() as conn:
            return await get_instructions(conn, instruction_ids, redis, bypass_cache)

    async def _get_rubrics() -> list:
        if not rubric_ids:
            return []
        async with pool.acquire() as conn:
            return await get_rubrics(conn, rubric_ids, redis, bypass_cache)

    (
        models,
        tools,
        prompts_list,
        instructions_list,
        rubrics_list,
    ) = await asyncio.gather(
        _get_models(),
        _get_tools(),
        _get_prompts(),
        _get_instructions(),
        _get_rubrics(),
    )

    # Collect IDs for final level
    provider_ids = list({m.provider_id for m in models if m.provider_id})
    args_ids = list({aid for t in tools for aid in (t.args_ids or [])})
    args_output_ids = list({aoid for t in tools for aoid in (t.args_output_ids or [])})

    # Step 4: parallel fetch providers + args + args_outputs

    async def _get_providers() -> list:
        if not provider_ids:
            return []
        async with pool.acquire() as conn:
            return await get_providers(conn, provider_ids, redis, bypass_cache)

    async def _get_args() -> list:
        if not args_ids:
            return []
        async with pool.acquire() as conn:
            return await get_args(conn, args_ids, redis, bypass_cache)

    async def _get_args_outputs() -> list:
        if not args_output_ids:
            return []
        async with pool.acquire() as conn:
            return await get_args_outputs(conn, args_output_ids, redis, bypass_cache)

    providers, args_list, args_outputs_list = await asyncio.gather(
        _get_providers(),
        _get_args(),
        _get_args_outputs(),
    )

    return SystemContext(
        system_id=system_id,
        agents=agents,
        models=models,
        providers=providers,
        tools=tools,
        args=args_list,
        args_outputs=args_outputs_list,
        prompts=prompts_list,
        instructions=instructions_list,
        rubrics=rubrics_list,
    )
