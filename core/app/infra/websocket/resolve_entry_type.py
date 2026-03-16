"""Resolve entry type from generation event data."""

from typing import Any

ENTRY_TYPE_ALIASES: dict[str, str] = {}


def resolve_entry_type(data: dict[str, Any]) -> str | None:
    """Extract and resolve entry_type from event data.

    Checks result.entry_type first (set by tool_executor), then
    falls back to the top-level entry_type from the payload.
    Applies aliases if any are defined.
    """
    result = data.get("result") or {}
    entry_type = result.get("entry_type") or data.get("entry_type")
    if entry_type:
        entry_type = ENTRY_TYPE_ALIASES.get(entry_type, entry_type)
    return entry_type
