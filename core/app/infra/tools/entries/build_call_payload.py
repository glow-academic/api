"""Build the structured payload for a call receipt."""

from typing import Any
from uuid import UUID


def build_call_payload(
    call_id: UUID,
    tool_id: UUID,
    arguments: dict[str, Any],
    output: dict[str, Any],
    raw_output: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Build the call receipt payload dict.

    Returns a dict with five keys:
    call_id, tool_id, arguments, output, raw_output.

    output: rendered template string (for display/grading) or raw dict.
    raw_output: full API response dict (for idempotent playback).
    """
    return {
        "call_id": str(call_id),
        "tool_id": str(tool_id),
        "arguments": arguments,
        "output": output,
        "raw_output": raw_output if raw_output is not None else output,
    }
