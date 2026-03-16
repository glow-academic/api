"""In-memory registry for tool call RPC between token factory and domain handlers."""

from __future__ import annotations

import asyncio
from typing import Any

_tool_results: dict[str, dict[str, Any]] = {}
_tool_futures: dict[str, asyncio.Future[dict[str, Any]]] = {}


def _get_future(call_id: str) -> asyncio.Future[dict[str, Any]]:
    fut = _tool_futures.get(call_id)
    if fut is None or fut.done():
        fut = asyncio.get_running_loop().create_future()
        _tool_futures[call_id] = fut
    return fut


def resolve_tool_result(call_id: str, result: dict[str, Any]) -> None:
    """Resolve a tool result for a given call_id."""
    _tool_results[call_id] = result
    fut = _tool_futures.get(call_id)
    if fut is not None and not fut.done():
        fut.set_result(result)


async def wait_for_tool_result(
    call_id: str, timeout_seconds: float
) -> dict[str, Any] | None:
    """Wait for a tool result to be provided by domain handlers."""
    if call_id in _tool_results:
        return _tool_results.pop(call_id)

    fut = _get_future(call_id)
    try:
        result = await asyncio.wait_for(fut, timeout=timeout_seconds)
    except TimeoutError:
        return None
    finally:
        _tool_futures.pop(call_id, None)
        _tool_results.pop(call_id, None)

    return result
