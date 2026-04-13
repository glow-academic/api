"""Clean tool output content for grading agent consumption.

Strips grading-irrelevant metadata from tool call JSON outputs
while preserving the structure needed for evaluation.
Full files remain on disk for audit — this only cleans the
content returned to the grading agent.
"""

from __future__ import annotations

import json

# Keys to drop entirely (UI metadata, internal linkage, timestamps)
_DROP_KEYS = frozenset({
    "suggestions",
    "show_ai_generate",
    "tool_id",
    "link_tool_id",
    "show",
    "required",
    "created_at",
    "mcp",
    "generated",
    "active",
    "conditional_parameter_ids",
    "department_ids",
    "show_ai_generate",
    "basic_show_ai_generate",
    "content_show_ai_generate",
    "parameters_step_show_ai_generate",
    "args_show_ai_generate",
    "arg_positions_show_ai_generate",
    "args_outputs_show_ai_generate",
    "resolved_parameter_ids",
    "events",
})

# Max items to keep in arrays before truncating
_MAX_ARRAY_ITEMS = 3


def clean_for_grading(raw: str) -> str:
    """Clean raw JSON/text content for grading agent.

    Returns cleaned string. If content isn't valid JSON,
    returns it as-is (might be plain text).
    """
    try:
        data = json.loads(raw)
    except (json.JSONDecodeError, TypeError):
        # Plain text — return as-is but truncate if huge
        if len(raw) > 4000:
            return raw[:4000] + f"\n\n... (truncated, {len(raw)} chars total)"
        return raw

    cleaned = _clean_value(data)
    return json.dumps(cleaned, indent=2, default=str)


def _clean_value(value):
    """Recursively clean a value."""
    if isinstance(value, dict):
        return _clean_dict(value)
    if isinstance(value, list):
        return _clean_list(value)
    return value


def _clean_dict(d: dict) -> dict:
    """Clean a dict: drop bloat keys and None values, recurse."""
    result = {}
    for key, value in d.items():
        if key in _DROP_KEYS:
            continue
        if value is None:
            continue
        result[key] = _clean_value(value)
    return result


def _clean_list(lst: list) -> list:
    """Clean a list: truncate long arrays, recurse into items."""
    cleaned = [_clean_value(item) for item in lst[:_MAX_ARRAY_ITEMS]]
    if len(lst) > _MAX_ARRAY_ITEMS:
        cleaned.append(f"... ({len(lst)} total)")
    return cleaned
