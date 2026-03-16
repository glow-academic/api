"""Shared utilities for tool call processing.

Used by both generate_artifact.py (text/call modality) and the audio emitter
(realtime adapter) to parse streaming tool call arguments and resolve output fields.
"""

import json
import re
from typing import Any


def extract_template_var(template: str) -> str | None:
    """Extract variable name from a Jinja template like '{{ content }}'."""
    match = re.search(r"\{\{\s*([a-zA-Z_][a-zA-Z0-9_]*)", template)
    return match.group(1) if match else None


def resolve_output_fields(
    parsed_args: dict[str, Any] | None,
    tool_name: str | None,
    tool_output_schemas: dict[str, dict[str, str]],
) -> dict[str, Any] | None:
    """Resolve output schema fields from parsed tool arguments."""
    if not parsed_args or not tool_name or tool_name not in tool_output_schemas:
        return None
    schema = tool_output_schemas[tool_name]
    resolved = {
        col: parsed_args[arg] for col, arg in schema.items() if arg in parsed_args
    }
    return resolved or None


def parse_partial_json(partial: str) -> dict[str, Any] | None:
    """Parse partial JSON by closing open strings and structures.

    Handles streaming tool call arguments that are incomplete JSON.
    Returns the parsed dict if successful, None otherwise.
    """
    if not partial or not partial.strip():
        return None

    candidate = partial.rstrip()

    # Try as-is first (might already be complete)
    try:
        result = json.loads(candidate)
        return result if isinstance(result, dict) else None
    except json.JSONDecodeError:
        pass

    # Walk the string tracking state to figure out what closings are needed
    in_string = False
    escape_next = False
    open_stack: list[str] = []

    for ch in candidate:
        if escape_next:
            escape_next = False
            continue
        if ch == "\\" and in_string:
            escape_next = True
            continue
        if ch == '"':
            in_string = not in_string
            continue
        if not in_string:
            if ch == "{":
                open_stack.append("}")
            elif ch == "[":
                open_stack.append("]")
            elif ch in ("}", "]") and open_stack:
                open_stack.pop()

    # Close open string if needed
    if in_string:
        candidate += '"'

    # Close open structures
    for closer in reversed(open_stack):
        candidate += closer

    try:
        result = json.loads(candidate)
        return result if isinstance(result, dict) else None
    except json.JSONDecodeError:
        return None


def build_tool_output_schemas(
    tools: list[dict[str, Any]],
) -> dict[str, dict[str, str]]:
    """Build tool_name → {output_column: argument_name} from tool definitions.

    Extracts the _args_outputs mapping from each tool definition to create
    a schema used by resolve_output_fields during streaming.
    """
    schemas: dict[str, dict[str, str]] = {}
    for tool_def in tools:
        if not isinstance(tool_def, dict):
            continue
        t_name = tool_def.get("name")
        t_args_outputs = tool_def.get("_args_outputs")
        if t_name and isinstance(t_args_outputs, list):
            resolved: dict[str, str] = {}
            for ao in t_args_outputs:
                if not isinstance(ao, dict):
                    continue
                col = ao.get("name")
                template = ao.get("template")
                if col and template:
                    arg_name = extract_template_var(template)
                    if arg_name:
                        resolved[col] = arg_name
            if resolved:
                schemas[t_name] = resolved
    return schemas
