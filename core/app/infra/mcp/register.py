"""MCP tool registration — dispatches through execute_infra_operation.

Each MCP tool registered here maps to an (artifact, operation) pair in
INFRA_OPS. At call time the handler:

  1. Resolves the caller's MCP context (profile → primary department →
     setting → mcp_resource → agent → enriched tool_defs).
  2. Rejects if the caller's agent doesn't expose this (artifact, operation)
     or the caller lacks the permission.
  3. Builds an InfraOperationSpec via resolve_tool_spec() and dispatches
     through execute_infra_operation() — the canonical path also used by
     HTTP routes, WebSocket handlers, and the generate pipeline.

Startup registration covers the superset of INFRA_OPS pairs. Per-caller
scoping happens at call time, not at registration (FastMCP stateless_http
doesn't expose per-session registration hooks).
"""

from __future__ import annotations

import logging
from typing import Any
from uuid import UUID

from mcp.server.fastmcp import FastMCP
from mcp.types import ToolAnnotations

from app.infra.mcp.resolve import resolve_mcp_context
from app.infra.tools.execute_infra_operation import (
    InfraContext,
    execute_infra_operation,
)
from app.infra.tools.resolve_tool_spec import resolve_tool_spec
from app.registry.operations import is_write_operation

logger = logging.getLogger(__name__)


def _find_tool_def(
    tool_defs: list[dict[str, Any]],
    artifact: str,
    operation: str,
) -> dict[str, Any] | None:
    """Return the first tool_def whose _permissions include (artifact, operation)."""
    target = (artifact, operation)
    for td in tool_defs:
        perms = td.get("_permissions") or []
        for p in perms:
            if (p.get("artifact"), p.get("operation")) == target:
                return td
    return None


def _annotations_for(operation: str, title: str) -> ToolAnnotations:
    is_write = is_write_operation(operation)
    return ToolAnnotations(
        title=title,
        readOnlyHint=not is_write,
        destructiveHint=operation == "delete",
        idempotentHint=operation in {"get", "search", "update", "delete"},
    )


async def _dispatch(
    artifact: str,
    operation: str,
    inputs: dict[str, Any],
) -> dict[str, Any]:
    """Resolve caller context, validate, and dispatch via execute_infra_operation."""
    from app.infra.globals import get_pool, get_redis_client
    from app.utils.mcp.get_mcp_profile_id import get_mcp_profile_id

    pool = get_pool()
    redis = get_redis_client()
    if pool is None or redis is None:
        return {"error": "server_unavailable", "status": "error"}

    try:
        profile_id = UUID(get_mcp_profile_id())
    except Exception as e:
        return {"error": f"profile_unavailable: {e}", "status": "error"}

    mcp_ctx = await resolve_mcp_context(pool, redis, profile_id)

    if mcp_ctx.agent_id is None:
        return {
            "error": "mcp_not_configured",
            "status": "error",
            "detail": "No MCP resource configured on this caller's primary department setting.",
        }

    if (artifact, operation) not in set(mcp_ctx.role_permissions):
        return {
            "error": "permission_denied",
            "status": "error",
            "artifact": artifact,
            "operation": operation,
        }

    tool_def = _find_tool_def(mcp_ctx.tool_defs, artifact, operation)
    if tool_def is None:
        return {
            "error": "tool_not_on_agent",
            "status": "error",
            "artifact": artifact,
            "operation": operation,
            "agent_id": str(mcp_ctx.agent_id),
        }

    # Routing templates in _args_outputs may use {{ artifact }} / {{ operation }};
    # inject them so multi-permission tools route correctly. Single-permission
    # tools hardcode the values in their templates and ignore these.
    routed_inputs = {**inputs, "artifact": artifact, "operation": operation}

    try:
        spec = resolve_tool_spec(tool_def, routed_inputs)
    except ValueError as e:
        return {"error": f"spec_invalid: {e}", "status": "error"}

    ctx = InfraContext(pool=pool, redis=redis, profile_id=profile_id)

    try:
        results = await execute_infra_operation(ctx, spec)
    except Exception as e:
        logger.exception(f"MCP dispatch failed for ({artifact}, {operation})")
        return {"error": str(e), "status": "error", "type": type(e).__name__}

    if not results:
        return {"status": "ok"}
    first = results[0]
    return first.model_dump(mode="json")


def register_tools(
    server: FastMCP,
    tool_graph: list[tuple[str, str]],
) -> None:
    """Register one FastMCP tool per (artifact, operation) in the catalog.

    Each tool's handler closes over its (artifact, operation) and dispatches
    through execute_infra_operation at call time. Per-caller agent-scope
    and permission-scope enforcement also happen at call time.
    """
    for artifact, operation in tool_graph:
        _register_one(server, artifact, operation)


def _register_one(server: FastMCP, artifact: str, operation: str) -> None:
    """Register a single (artifact, operation) tool on the FastMCP server.

    Factored out so artifact/operation are captured by closure in a fresh
    scope — avoids late-binding bugs and keeps handler signature clean
    (FastMCP rejects parameter names starting with '_').
    """
    tool_name = f"{operation}_{artifact}"
    title = f"{artifact.title()} {operation.title()}"
    description = f"{operation} {artifact}"

    async def handler(
        kwargs: dict[str, Any] | None = None,
        **kw: Any,
    ) -> dict[str, Any]:
        payload = {**(kwargs or {}), **kw}
        return await _dispatch(artifact, operation, payload)

    handler.__name__ = tool_name
    handler.__qualname__ = tool_name
    handler.__doc__ = description

    server.tool(
        name=tool_name,
        title=title,
        description=description,
        annotations=_annotations_for(operation, title),
    )(handler)

    logger.debug(f"Registered MCP tool: {tool_name}")
