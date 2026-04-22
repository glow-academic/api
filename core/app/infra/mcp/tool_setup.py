"""Build enriched tool_defs from an agent_id.

Reuses the four enrichment functions from websocket/prepare_pipeline.py,
applied to a single agent's tools. The result has the same shape the
generate pipeline produces (convert_tools_to_dict + enrich_*), so it can
be passed directly to resolve_tool_spec() / execute_infra_operation().
"""

from __future__ import annotations

import asyncio
from typing import Any
from uuid import UUID

import asyncpg
from redis.asyncio import Redis

from app.infra.generation.render_developer_instructions import (
    convert_tools_to_dict,
)
from app.infra.websocket.prepare_pipeline import (
    enrich_tools_with_args,
    enrich_tools_with_args_outputs,
    enrich_tools_with_instruction_templates,
    enrich_tools_with_permissions,
)
from app.tools.resources.agents.get import get_agents as get_agent_resources
from app.tools.resources.args.get import get_args
from app.tools.resources.args_outputs.get import get_args_outputs
from app.tools.resources.instructions.get import get_instructions
from app.tools.resources.permissions.get import get_permissions
from app.tools.resources.tools.get import get_tools


async def build_agent_tool_defs(
    pool: asyncpg.Pool,
    redis: Redis,
    agent_resource_id: UUID,
    bypass_cache: bool = False,
) -> list[dict[str, Any]]:
    """Return enriched tool_defs for the agent's selected tools.

    The caller passes an agents_resource id (the denormalized snapshot).
    Chain:
      1. agents_resource → tool_ids (already on the snapshot)
      2. tools_resource rows (active only)
      3. batch-fetch args / args_outputs / permissions / instructions
      4. run the four enrichers
    """
    async with pool.acquire() as conn:
        resources = await get_agent_resources(conn, [agent_resource_id], redis, bypass_cache)
    if not resources:
        return []

    tool_ids = list(resources[0].tool_ids or [])
    if not tool_ids:
        return []

    async with pool.acquire() as conn:
        tools = await get_tools(conn, tool_ids, redis, bypass_cache)
    tools = [t for t in tools if t.active]
    if not tools:
        return []

    arg_ids = list({aid for t in tools for aid in (t.args_ids or [])})
    arg_output_ids = list({aid for t in tools for aid in (t.args_output_ids or [])})
    perm_ids = list({pid for t in tools for pid in (t.permission_ids or [])})
    instruction_ids = list({t.instruction_id for t in tools if t.instruction_id})

    async def _fetch_args() -> list:
        async with pool.acquire() as conn:
            return await get_args(conn, arg_ids, redis, bypass_cache)

    async def _fetch_args_outputs() -> list:
        async with pool.acquire() as conn:
            return await get_args_outputs(conn, arg_output_ids, redis, bypass_cache)

    async def _fetch_permissions() -> list:
        async with pool.acquire() as conn:
            return await get_permissions(conn, perm_ids, redis, bypass_cache)

    async def _fetch_instructions() -> list:
        async with pool.acquire() as conn:
            return await get_instructions(conn, instruction_ids, redis, bypass_cache)

    args, args_outputs, permissions, instructions = await asyncio.gather(
        _fetch_args(),
        _fetch_args_outputs(),
        _fetch_permissions(),
        _fetch_instructions(),
    )

    tool_dicts = convert_tools_to_dict(tools) or []
    tool_dicts = enrich_tools_with_args(tool_dicts, tools, args)
    tool_dicts = enrich_tools_with_args_outputs(tool_dicts, tools, args_outputs)
    tool_dicts = enrich_tools_with_permissions(tool_dicts, tools, permissions)
    tool_dicts = enrich_tools_with_instruction_templates(
        tool_dicts, tools, {i.id: i for i in instructions}
    )

    return tool_dicts
