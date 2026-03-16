"""Build the structured payload for a call receipt."""

from typing import Any
from uuid import UUID


def build_call_payload(
    call_id: UUID,
    tool_id: UUID,
    arguments: dict[str, Any],
    output: dict[str, Any],
) -> dict[str, Any]:
    """Build the call receipt payload dict.

    Returns a dict with exactly four keys:
    call_id, tool_id, arguments, output.
    """
    return {
        "call_id": str(call_id),
        "tool_id": str(tool_id),
        "arguments": arguments,
        "output": output,
    }
