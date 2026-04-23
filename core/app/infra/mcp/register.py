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
import inspect
import logging
from typing import Annotated, Any
from uuid import UUID

from mcp.server.fastmcp import FastMCP
from mcp.types import ToolAnnotations
from pydantic import Field

from app.infra.mcp.resolve import resolve_mcp_context
from app.infra.mcp.tool_catalog import slugify_tool_name
from app.infra.tools.execute_infra_operation import (
    InfraContext,
    execute_infra_operation,
)
from app.infra.tools.render_result import render_tool_result
from app.infra.tools.resolve_tool_spec import resolve_tool_spec
from app.registry.operations import is_write_operation

logger = logging.getLogger(__name__)

# Map args_resource.field_type values to Python types for inputSchema inference.
_FIELD_TYPE_MAP: dict[str, type] = {
    "string": str,
    "str": str,
    "text": str,
    "uuid": str,
    "integer": int,
    "int": int,
    "number": float,
    "float": float,
    "boolean": bool,
    "bool": bool,
    "array": list,
    "list": list,
    "object": dict,
    "dict": dict,
}


def _py_type_for(field_type: str | None) -> type:
    return _FIELD_TYPE_MAP.get((field_type or "string").lower(), str)

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

    ctx = InfraContext(
        pool=pool,
        redis=redis,
        profile_id=profile_id,
        instruction_template=td.get("_instruction_template"),
    )
    try:
        results = await execute_infra_operation(ctx, spec)
    except Exception as e:
        logger.exception(f"MCP dispatch failed for tool '{tool_name}'")
        return {"error": str(e), "status": "error", "type": type(e).__name__}

    # Layer 3 output render — LLM sees the rendered instruction template
    # when present, JSON fallback otherwise. Shared with generate.
    return render_tool_result(td, results)


def _routing_args(td: dict[str, Any]) -> dict[str, dict[str, Any]]:
    """Return `artifact`/`operation` args for multi-target tools.

    When a tool's permissions cover more than one artifact (or more than
    one operation), the LLM must specify which target it wants. These
    aren't in `td["arguments"]` — they're routing inputs consumed by the
    Jinja templates in `td["_args_outputs"]`. We surface them explicitly.
    """
    perms = td.get("_permissions") or []
    artifacts = sorted({p.get("artifact") for p in perms if p.get("artifact")})
    operations = sorted({p.get("operation") for p in perms if p.get("operation")})

    extras: dict[str, dict[str, Any]] = {}
    if len(artifacts) > 1:
        extras["artifact"] = {
            "type": "string",
            "required": True,
            "description": f"Target artifact. Allowed: {', '.join(artifacts)}.",
        }
    if len(operations) > 1:
        extras["operation"] = {
            "type": "string",
            "required": True,
            "description": f"Target operation. Allowed: {', '.join(operations)}.",
        }
    return extras


def _build_signature_params(td: dict[str, Any]) -> list[inspect.Parameter]:
    """Build the typed keyword-only parameters FastMCP introspects.

    Each arg from `td["arguments"]` becomes a top-level parameter annotated
    with `Annotated[T, Field(description=..., default=...)]`. Multi-target
    tools also get `artifact` and `operation` surfaced explicitly.
    """
    arg_specs = td.get("arguments") or {}
    arg_descs = td.get("argument_descriptions") or {}
    arg_defaults = td.get("argument_defaults") or {}
    params: list[inspect.Parameter] = []

    # Routing args win: when a tool covers >1 artifact/operation, we override
    # the seed's generic "e.g. persona, scenario" with an enumerated allowed
    # list AND promote it to required=True. Order matters — routing last so it
    # overrides any seed-declared artifact/operation entries.
    routing = _routing_args(td)
    merged = {**arg_specs, **routing}
    for arg_name, info in merged.items():
        py_type = _py_type_for(info.get("type"))
        required = bool(info.get("required", False))
        description = info.get("description") or arg_descs.get(arg_name, "")
        default_value = arg_defaults.get(arg_name)
        annotation = Annotated[py_type, Field(description=description)]

        if required and default_value is None:
            default = inspect.Parameter.empty
        else:
            default = default_value

        params.append(
            inspect.Parameter(
                name=arg_name,
                kind=inspect.Parameter.KEYWORD_ONLY,
                annotation=annotation,
                default=default,
            )
        )
    return params


def _register_one(server: FastMCP, td: dict[str, Any]) -> None:
    """Register a single FastMCP tool with a typed, introspectable signature."""
    name = td.get("name")
    if not name:
        return
    tool_slug = slugify_tool_name(name)
    if not tool_slug:
        return
    description = td.get("description") or name

    params = _build_signature_params(td)

    async def handler(**kwargs: Any) -> dict[str, Any]:
        # Drop None-valued kwargs so resolve_tool_spec + downstream Pydantic
        # defaults apply cleanly. FastMCP passes absent-but-optional fields
        # as None by default, which would otherwise overwrite defaults.
        inputs = {k: v for k, v in kwargs.items() if v is not None}
        return await _dispatch(tool_slug, inputs)

    handler.__name__ = tool_slug
    handler.__qualname__ = tool_slug
    handler.__doc__ = description
    handler.__signature__ = inspect.Signature(  # type: ignore[attr-defined]
        parameters=params, return_annotation=dict
    )
    handler.__annotations__ = {p.name: p.annotation for p in params} | {"return": dict}

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
