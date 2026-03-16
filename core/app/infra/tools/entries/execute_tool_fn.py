"""Execute an arbitrary tool function and capture output."""

import json
from collections.abc import Callable
from typing import Any

import asyncpg  # type: ignore


async def execute_tool_fn(
    tool_fn: Callable[..., Any],
    conn: asyncpg.Connection,
    arguments: dict[str, Any],
) -> str:
    """Call *tool_fn* with conn + arguments and return a JSON string.

    Always returns valid JSON — on success the tool's own output,
    on failure an error envelope.
    """
    try:
        result = await tool_fn(conn, **arguments)
        if isinstance(result, str):
            return result
        return json.dumps(result, default=str)
    except Exception as e:
        return json.dumps(
            {
                "success": False,
                "message": f"Tool execution error: {e}",
            }
        )
