"""Tool executor — registry-based tool execution via create_tool_call black box.

Flow:
  1. Render Jinja templates (model args → mapped kwargs)
  2. Resolve black-box function from tool_fns registry
  3. Inject infrastructure kwargs (soft, mcp, redis)
  4. Delegate to create_tool_call (execute fn → uploads → run/call/message chain)

Supports soft=True for dormant record creation (generation pipeline).
"""

from __future__ import annotations

import json
import uuid
from pathlib import Path
from typing import Any

import asyncpg

from app.infra.artifacts.discovery import map_template_values_to_table_columns
from app.infra.globals import get_redis_client
from app.infra.tools.entries.create_tool_call import create_tool_call
from app.infra.tools.render_tool_template import render_tool_template
from app.registry.tool_fns import resolve_tool_fn
from app.utils.logging.db_logger import get_logger

logger = get_logger(__name__)


async def execute_tool_call(
    conn: asyncpg.Connection,
    tool_name: str,
    arguments: dict[str, Any],
    tool_id: uuid.UUID,
    *,
    group_id: uuid.UUID,
    session_id: uuid.UUID,
    profile_id: uuid.UUID,
    upload_folder: Path,
    run_id: uuid.UUID | None = None,
    resource_type: str | None = None,
    entry_type: str | None = None,
    is_creatable: bool | None = None,
    soft: bool = False,
    mcp: bool = False,
) -> str:
    """Execute a tool call via registry lookup + create_tool_call black box.

    Flow:
      1. Render Jinja templates (model args → mapped kwargs)
      2. Resolve black-box function from tool_fns registry
      3. Inject infrastructure kwargs (soft, mcp, redis)
      4. Delegate to create_tool_call which handles everything:
         execute fn → write uploads → create run/call/message chain

    Returns JSON string for model consumption.
    """
    try:
        # Determine layer and operation
        if entry_type:
            layer = "entry"
            name = entry_type
        elif resource_type:
            layer = "resource"
            name = resource_type
        else:
            return json.dumps(
                {
                    "success": False,
                    "message": f"No resource_type or entry_type for tool: {tool_name}",
                    "error_stage": "tool_resolve",
                }
            )

        operation = "create" if (is_creatable is None or is_creatable) else "search"

        # 1. Render templates (model args → mapped kwargs)
        rendered_values = await render_tool_template(conn, tool_id, arguments)
        mapped_values = await map_template_values_to_table_columns(
            conn,
            name,
            rendered_values,
            tool_id=str(tool_id),
            is_entry=(layer == "entry"),
        )

        if not mapped_values and operation == "create":
            return json.dumps(
                {
                    "success": False,
                    "message": f"No values to insert for {tool_name}. Check tool configuration.",
                    "error_stage": "tool_execute",
                }
            )

        # 2. Resolve black-box function from registry
        tool_fn = resolve_tool_fn(layer, name, operation)
        if tool_fn is None:
            return json.dumps(
                {
                    "success": False,
                    "message": f"No registered tool function for ({layer}, {name}, {operation})",
                    "error_stage": "tool_resolve",
                }
            )

        # 3. Inject infrastructure kwargs
        fn_arguments: dict[str, Any] = {**mapped_values, "soft": soft, "mcp": mcp}

        # Resources need redis for cache invalidation
        if layer == "resource":
            fn_arguments["redis"] = get_redis_client()

        # 4. Delegate to create_tool_call (handles everything)
        result = await create_tool_call(
            conn,
            group_id=group_id,
            session_id=session_id,
            profile_id=profile_id,
            upload_folder=upload_folder,
            tool_fn=tool_fn,
            arguments=fn_arguments,
            tool_id=tool_id,
            mcp=mcp,
        )

        result_id_str = str(result.result_id) if result.result_id else None
        response: dict[str, Any] = {
            "success": True,
            "message": f"Successfully created {name} {layer}",
            "result_id": result_id_str,
            "run_id": str(result.run_id),
            "call_id": str(result.call_id) if result.call_id else None,
            "message_id": str(result.message_id),
            f"{layer}_type": name,
            "soft": soft,
        }
        # Emit layer-specific ID key for downstream consumers
        # (generation_progress reads resource_id / entry_id)
        if layer == "resource":
            response["resource_id"] = result_id_str
        elif layer == "entry":
            response["entry_id"] = result_id_str
        return json.dumps(response)

    except Exception as e:
        logger.exception(f"Error executing tool {tool_name}: {e}")
        return json.dumps(
            {
                "success": False,
                "message": f"Tool execution error: {str(e)}",
                "error_stage": "tool_execute",
            }
        )
