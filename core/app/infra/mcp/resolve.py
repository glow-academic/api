"""Resolve an MCP caller's context from profile_id.

Walks the black-box chain:
  profile → primary department's settings_id
          → get_settings(mcp=True).mcp_ids (junction)
          → get_mcp() → mcp_resource.agent_id
          → build_agent_tool_defs(agent_id) → enriched tool_defs

Returns an McpContext with the profile's role_permissions alongside the
agent's tool_defs, so the MCP call handler can enforce both agent-scope
and permission-scope before dispatching through execute_infra_operation.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from uuid import UUID

import asyncpg
from redis.asyncio import Redis

from app.infra.mcp.tool_setup import build_agent_tool_defs
from app.infra.profile_identity_context import resolve_profile_identity_context
from app.tools.artifacts.setting.get import get_settings
from app.tools.resources.mcp.get import get_mcp


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

    primary_department_id = identity.primary_department_id
    role_permissions = list(identity.role_permissions)

    if identity.settings_id is None:
        return McpContext(
            profile_id=profile_id,
            primary_department_id=primary_department_id,
            role_permissions=role_permissions,
        )

    async with pool.acquire() as conn:
        settings = await get_settings(
            conn, [identity.settings_id], mcp=True
        )
    if not settings:
        return McpContext(
            profile_id=profile_id,
            primary_department_id=primary_department_id,
            role_permissions=role_permissions,
        )

    mcp_ids = list(settings[0].mcp_ids or [])
    if not mcp_ids:
        return McpContext(
            profile_id=profile_id,
            primary_department_id=primary_department_id,
            role_permissions=role_permissions,
        )

    async with pool.acquire() as conn:
        mcp_resources = await get_mcp(conn, mcp_ids, redis, bypass_cache)
    agent_id = next(
        (m.agent_id for m in mcp_resources if m.active and m.agent_id),
        None,
    )
    if agent_id is None:
        return McpContext(
            profile_id=profile_id,
            primary_department_id=primary_department_id,
            role_permissions=role_permissions,
        )

    tool_defs = await build_agent_tool_defs(
        pool, redis, agent_id, bypass_cache=bypass_cache
    )

    return McpContext(
        profile_id=profile_id,
        primary_department_id=primary_department_id,
        agent_id=agent_id,
        tool_defs=tool_defs,
        role_permissions=role_permissions,
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
