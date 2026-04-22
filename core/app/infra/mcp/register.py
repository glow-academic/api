"""MCP tool registration — one FastMCP tool per tool_def.

The catalog is the system-wide enriched tool_def list (see tool_catalog).
Each unique tool.name becomes one MCP tool. Per-caller scoping in
ScopedFastMCP filters to the subset present on the caller's agent.

Call handler, identical to the generate pipeline's tool dispatch:

  resolve_tool_spec(td, inputs)        -> InfraOperationSpec
  execute_infra_operation(ctx, spec)   -> canonical dispatch

Multi-target tools route internally via their _args_outputs Jinja
templates — the LLM supplies `artifact` and `operation` as inputs when
the tool covers more than one pair.
"""

from __future__ import annotations

import asyncio
import logging
from typing import Any
from uuid import UUID

from mcp.server.fastmcp import FastMCP
from mcp.types import ToolAnnotations

from app.infra.mcp.resolve import resolve_mcp_context
from app.infra.mcp.tool_catalog import slugify_tool_name
from app.infra.tools.execute_infra_operation import (
    InfraContext,
    execute_infra_operation,
)
from app.infra.tools.resolve_tool_spec import resolve_tool_spec
from app.registry.operations import is_write_operation

logger = logging.getLogger(__name__)

_ensure_lock = asyncio.Lock()
_ensured = False


async def ensure_registered(server: FastMCP) -> None:
    """Register MCP tools from the DB once, on first MCP request.

    Deferred to first request because module-load time precedes DB pool
    initialization.
    """
    global _ensured
    if _ensured:
        return
    async with _ensure_lock:
        if _ensured:
            return
        from app.infra.globals import get_pool, get_redis_client
        from app.infra.mcp.tool_catalog import build_mcp_tool_catalog

        pool = get_pool()
        redis = get_redis_client()
        if pool is None or redis is None:
            logger.warning("MCP registration skipped: pool/redis not ready")
            return

        try:
            tool_defs = await build_mcp_tool_catalog(pool, redis)
        except Exception:
            logger.exception("Failed to build MCP tool catalog")
            return

        registered = 0
        for td in tool_defs:
            try:
                _register_one(server, td)
                registered += 1
            except Exception as e:
                logger.debug(f"Skipping MCP tool '{td.get('name', '?')}': {e}")
        logger.info(f"Registered {registered} MCP tools")
        _ensured = True


def _annotations_for(td: dict[str, Any], title: str) -> ToolAnnotations:
    """Derive MCP annotations from the tool's permissions.

    Conservative rules: any write permission → not read-only; any delete
    → destructive; all permissions idempotent → idempotent.
    """
    perms = td.get("_permissions") or []
    operations = [p.get("operation", "") for p in perms]
    any_write = any(is_write_operation(op) for op in operations)
    any_delete = any(op == "delete" for op in operations)
    all_idempotent = bool(operations) and all(
        op in {"get", "search", "update", "delete"} for op in operations
    )
    return ToolAnnotations(
        title=title,
        readOnlyHint=not any_write,
        destructiveHint=any_delete,
        idempotentHint=all_idempotent,
    )


async def _dispatch(tool_name: str, inputs: dict[str, Any]) -> dict[str, Any]:
    """Resolve the caller's agent tool_def by name, validate, dispatch."""
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
            "detail": "No MCP resource on this caller's department setting.",
        }

    td = next(
        (t for t in mcp_ctx.tool_defs if slugify_tool_name(t.get("name", "")) == tool_name),
        None,
    )
    if td is None:
        return {
            "error": "tool_not_on_agent",
            "status": "error",
            "tool": tool_name,
            "agent_id": str(mcp_ctx.agent_id),
        }

    try:
        spec = resolve_tool_spec(td, inputs)
    except ValueError as e:
        return {"error": f"spec_invalid: {e}", "status": "error"}

    # Belt-and-suspenders: enforce the RESOLVED (artifact, operation) against
    # the profile's role permissions. resolve_tool_spec already validated
    # against the tool's own permissions; this enforces caller-level authz.
    target = spec.targets[0]
    if (target.artifact, target.operation) not in set(mcp_ctx.role_permissions):
        return {
            "error": "permission_denied",
            "status": "error",
            "artifact": target.artifact,
            "operation": target.operation,
        }

    ctx = InfraContext(pool=pool, redis=redis, profile_id=profile_id)
    try:
        results = await execute_infra_operation(ctx, spec)
    except Exception as e:
        logger.exception(f"MCP dispatch failed for tool '{tool_name}'")
        return {"error": str(e), "status": "error", "type": type(e).__name__}

    if not results:
        return {"status": "ok"}
    return results[0].model_dump(mode="json")


def _register_one(server: FastMCP, td: dict[str, Any]) -> None:
    """Register a single FastMCP tool for this tool_def."""
    name = td.get("name")
    if not name:
        return
    tool_slug = slugify_tool_name(name)
    if not tool_slug:
        return
    description = td.get("description") or name

    async def handler(
        kwargs: dict[str, Any] | None = None,
        **kw: Any,
    ) -> dict[str, Any]:
        payload = {**(kwargs or {}), **kw}
        return await _dispatch(tool_slug, payload)

    handler.__name__ = tool_slug
    handler.__qualname__ = tool_slug
    handler.__doc__ = description

    server.tool(
        name=tool_slug,
        title=name,
        description=description,
        annotations=_annotations_for(td, title=name),
    )(handler)


def register_tools(server: FastMCP, tool_defs: list[dict[str, Any]]) -> None:
    """Register an explicit list of tool_defs — used by tests.

    Production code uses ensure_registered() which lazily builds the
    catalog from the DB on first MCP request.
    """
    for td in tool_defs:
        try:
            _register_one(server, td)
        except Exception as e:
            logger.debug(f"Skipping tool '{td.get('name', '?')}': {e}")
