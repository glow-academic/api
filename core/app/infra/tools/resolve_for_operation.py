"""Permission-driven, agent-independent tool resolution for audit attribution.

Today's :func:`app.infra.events.audit.resolve_artifact_operation_tool`
walks ``tool_graph.tools`` — a list built by traversing
``settings → systems → agents → agent.tool_ids``. That's the right
shape for "which tool can THIS agent call?" (a generation/dispatch
concern), but it bakes in agent context that doesn't apply to HTTP
or WS callers firing audit events.

This helper answers a different question: "what's the canonical tool
in the system for ``(artifact, operation)``?" — independent of any
agent, any settings, any dispatch context. The bridge is **permissions**:

  * Every tool owns ``permission_ids``.
  * Every permission owns ``(artifact, operation)``.
  * A tool is a candidate for an audit event iff one of its
    permissions matches that event's ``(artifact, operation)``.

Among candidates, we pick the most-specific tool: smallest
``array_length(permission_ids)`` first, with ``name`` as a stable
tie-break. Rationale: a tool with one permission is laser-targeted at
that operation; a tool with fifty permissions probably exposes this
operation as a side-effect of a broader surface.

If no tool exists for an operation, that's fine — :func:`create_tool_call`
falls back to writing the raw output. Not every audited event needs a
registered tool.
"""

from __future__ import annotations

from dataclasses import dataclass
from uuid import UUID

import asyncpg
from redis.asyncio import Redis

from app.tools.resources.instructions.get import get_instructions
from app.tools.resources.permissions.search import search_permissions
from app.tools.resources.tools.get import get_tools


@dataclass(frozen=True)
class ResolvedOperationTool:
    """The tool that owns the canonical permission for an audit event."""

    tool_id: UUID
    instruction_id: UUID | None
    instruction_template: str | None


async def resolve_tool_for_operation(
    conn: asyncpg.Connection,
    redis: Redis,
    *,
    artifact: str,
    operation: str,
) -> ResolvedOperationTool | None:
    """Return the canonical tool for an ``(artifact, operation)`` audit event.

    Permission-driven, agent-independent. Every HTTP or WS caller that
    funnels through ``run_artifact_operation_with_audit`` gets the right
    tool attached for free — no agent context required.

    Returns ``None`` when no tool in the system has a permission
    covering this operation. The audit path then falls through to
    raw-output rendering, which is the correct behavior for
    operations that don't have a registered tool.
    """
    # 1. Find permissions matching (artifact, operation). Typically 1
    #    (the seed has one permission row per artifact-operation pair),
    #    but tolerate N for forward-compat with custom permission setups.
    perms = await search_permissions(
        conn, redis, artifact=artifact, operation=operation,
    )
    if not perms:
        return None
    perm_ids = [p.id for p in perms]

    # 2. Find the most-specific tool whose permission_ids overlap.
    #    Composition first (search_tools) doesn't expose a permission_ids
    #    filter; this is a thin direct query against the resource table.
    #    Sort by permissions_count ASC (specificity), then name ASC,
    #    then id (stable across boots) so audit attribution is
    #    deterministic.
    row = await conn.fetchrow(
        """
        SELECT id
        FROM tools_resource
        WHERE active = true
          AND permission_ids && $1::uuid[]
        ORDER BY COALESCE(array_length(permission_ids, 1), 0) ASC,
                 name ASC,
                 id ASC
        LIMIT 1
        """,
        perm_ids,
    )
    if not row:
        return None

    # 3. Hydrate the tool row to get instruction_id + name (cached).
    tools = await get_tools(conn, [row["id"]], redis)
    if not tools:
        return None
    tool = tools[0]

    # 4. If the tool has an instruction_id, hydrate the template too
    #    (cached). The template is a Jinja string that
    #    ``create_tool_call`` renders with the call's arguments + output.
    instruction_id = getattr(tool, "instruction_id", None)
    instruction_template: str | None = None
    if instruction_id is not None:
        instructions = await get_instructions(conn, [instruction_id], redis)
        if instructions:
            tmpl = getattr(instructions[0], "template", None)
            if tmpl:
                instruction_template = tmpl

    return ResolvedOperationTool(
        tool_id=tool.id,
        instruction_id=instruction_id,
        instruction_template=instruction_template,
    )
