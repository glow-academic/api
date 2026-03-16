"""Resolve resource type from generation event data."""

from typing import Any

RESOURCE_TYPE_ALIASES: dict[str, str] = {"fields": "parameter_fields"}


def resolve_resource_type(data: dict[str, Any]) -> str | None:
    """Extract and resolve resource_type from event data.

    Checks result.resource_type first (set by tool_executor), then
    falls back to the top-level resource_type from the payload.
    Applies aliases (e.g., "fields" -> "parameter_fields").
    """
    result = data.get("result") or {}
    resource_type = result.get("resource_type") or data.get("resource_type")
    if resource_type:
        resource_type = RESOURCE_TYPE_ALIASES.get(resource_type, resource_type)
    return resource_type
