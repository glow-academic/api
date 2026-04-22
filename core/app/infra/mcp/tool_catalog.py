"""Build the system-wide MCP tool catalog from the DB.

Every active tools_resource row becomes one MCP tool (deduped by name).
The enrichment pipeline — args / args_outputs / permissions / instruction
templates — is the same one generate uses (websocket/prepare_pipeline),
so the MCP tool's inputSchema + routing + permissions mirror exactly what
the generate pipeline sees.

Produces a list of tool_def dicts ready for:
  - FastMCP registration (name, description, annotations derived per tool)
  - resolve_tool_spec(td, inputs) at call time
"""

from __future__ import annotations

import asyncio
from typing import Any

import asyncpg
from redis.asyncio import Redis

from app.infra.generation.render_developer_instructions import convert_tools_to_dict
from app.infra.websocket.prepare_pipeline import (
    enrich_tools_with_args,
    enrich_tools_with_args_outputs,
    enrich_tools_with_instruction_templates,
    enrich_tools_with_permissions,
)
from app.tools.resources.args.get import get_args
from app.tools.resources.args_outputs.get import get_args_outputs
from app.tools.resources.instructions.get import get_instructions
from app.tools.resources.permissions.get import get_permissions
from app.tools.resources.tools.get import get_tools
from app.tools.resources.tools.search import search_tools


async def build_mcp_tool_catalog(
    pool: asyncpg.Pool,
    redis: Redis,
    bypass_cache: bool = False,
) -> list[dict[str, Any]]:
    """Return the catalog of enriched tool_defs for FastMCP registration.

    Each entry is the same shape resolve_tool_spec() consumes: name,
    description, arguments (for inputSchema), _args_outputs (routing
    templates), _permissions (authz pairs), _instruction_template.

    Deduped by tool.name — tools with the same name across agents are
    assumed to have the same args/permissions (as they do in the seeds).
    """
    async with pool.acquire() as conn:
        tools = await search_tools(
            conn,
            redis,
            search=None,
            limit_count=100_000,
            bypass_cache=bypass_cache,
        )
    tools = [t for t in tools if t.active]
    if not tools:
        return []

    # Dedupe by tool.name — take the first occurrence.
    seen: set[str] = set()
    unique_tools: list[Any] = []
    for t in tools:
        if t.name and t.name not in seen:
            seen.add(t.name)
            unique_tools.append(t)

    arg_ids = list({aid for t in unique_tools for aid in (t.args_ids or [])})
    arg_output_ids = list(
        {aid for t in unique_tools for aid in (t.args_output_ids or [])}
    )
    perm_ids = list({pid for t in unique_tools for pid in (t.permission_ids or [])})
    instruction_ids = list(
        {t.instruction_id for t in unique_tools if t.instruction_id}
    )

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

    tool_dicts = convert_tools_to_dict(unique_tools) or []
    tool_dicts = enrich_tools_with_args(tool_dicts, unique_tools, args)
    tool_dicts = enrich_tools_with_args_outputs(
        tool_dicts, unique_tools, args_outputs
    )
    tool_dicts = enrich_tools_with_permissions(
        tool_dicts, unique_tools, permissions
    )
    tool_dicts = enrich_tools_with_instruction_templates(
        tool_dicts, unique_tools, {i.id: i for i in instructions}
    )

    return tool_dicts


def slugify_tool_name(name: str) -> str:
    """Convert a human tool name to an MCP wire name.

    "Activity Export" -> "activity_export"
    "Create Content"  -> "create_content"
    Non-alphanumeric collapses to a single underscore; leading/trailing
    underscores stripped; lowercased.
    """
    out: list[str] = []
    last_underscore = False
    for ch in name:
        if ch.isalnum():
            out.append(ch.lower())
            last_underscore = False
        else:
            if not last_underscore and out:
                out.append("_")
                last_underscore = True
    while out and out[-1] == "_":
        out.pop()
    return "".join(out)
