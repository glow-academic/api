"""Resolve an MCP caller's context from profile_id.

Canonical two-hop read, all through resource-level black boxes:

  profile_identity_context  → primary department → dept.setting_ids[0]
  get_settings (resource)   → settings_resource.mcp_id
  get_mcp (resource)        → mcp_resource.agent_id (agents_resource.id)
  build_agent_tool_defs     → enriched tool_defs

The MCP call handler enforces agent-scope + permission-scope using the
returned McpContext.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from uuid import UUID

import asyncpg
from redis.asyncio import Redis

from app.infra.mcp.tool_setup import build_agent_tool_defs
from app.infra.profile_identity_context import resolve_profile_identity_context
from app.tools.resources.mcp.get import get_mcp
from app.tools.resources.settings.get import get_settings


@dataclass(frozen=True)
class McpContext:
    """What an MCP caller is allowed to see and do."""

    profile_id: UUID
    primary_department_id: UUID | None = None
    agent_id: UUID | None = None
    tool_defs: list[dict] = field(default_factory=list)
    role_permissions: list[tuple[str, str]] = field(default_factory=list)


async def resolve_mcp_context(
    pool: asyncpg.Pool,
    redis: Redis,
    profile_id: UUID,
    bypass_cache: bool = False,
) -> McpContext:
    """Resolve the MCP tool surface + permissions for this caller.

    Returns an McpContext with empty tool_defs if any link in the chain
    is missing (no primary department, no setting, no MCP resource on
    the setting, or the agent has no tools).
    """
    identity = await resolve_profile_identity_context(
        pool, profile_id, redis, bypass_cache=bypass_cache
    )
    if identity is None:
        return McpContext(profile_id=profile_id)

    base = McpContext(
        profile_id=profile_id,
        primary_department_id=identity.primary_department_id,
        role_permissions=list(identity.role_permissions),
    )

    if identity.settings_id is None:
        return base

    async with pool.acquire() as conn:
        settings = await get_settings(
            conn, [identity.settings_id], redis, bypass_cache
        )
    mcp_id = settings[0].mcp_id if settings else None
    if mcp_id is None:
        return base

    async with pool.acquire() as conn:
        mcp_resources = await get_mcp(conn, [mcp_id], redis, bypass_cache)
    agent_resource_id = next(
        (m.agent_id for m in mcp_resources if m.active and m.agent_id),
        None,
    )
    if agent_resource_id is None:
        return base

    tool_defs = await build_agent_tool_defs(
        pool, redis, agent_resource_id, bypass_cache=bypass_cache
    )

    return McpContext(
        profile_id=profile_id,
        primary_department_id=identity.primary_department_id,
        agent_id=agent_resource_id,
        tool_defs=tool_defs,
        role_permissions=list(identity.role_permissions),
    )


def allowed_tool_names(ctx: McpContext) -> set[str]:
    """Return the MCP tool names the caller is actually authorized to call.

    A tool is allowed when its (artifact, operation) is on the agent AND
    in the profile's role permissions. Uses the canonical MCP tool naming
    convention: "{operation}_{artifact}".
    """
    role_perms = set(ctx.role_permissions)
    allowed: set[str] = set()
    for td in ctx.tool_defs:
        for perm in td.get("_permissions") or []:
            pair = (perm.get("artifact"), perm.get("operation"))
            if pair in role_perms:
                allowed.add(f"{pair[1]}_{pair[0]}")
    return allowed
