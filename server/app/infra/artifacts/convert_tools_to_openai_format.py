"""Convert database tool configs to LiteLLM tool formats."""

from typing import Any

from openai.types.responses.function_tool_param import FunctionToolParam

from app.infra.shared_types import IGetTextRunContextAndCreateRunV4Tool


def _get_tool_attr(tool: Any, attr: str, default: Any = None) -> Any:
    """Get attribute from tool, handling both object and dict formats."""
    if isinstance(tool, dict):
        return tool.get(attr, default)
    return getattr(tool, attr, default)


def convert_tools_to_openai_format(
    tools: list[IGetTextRunContextAndCreateRunV4Tool] | list[dict[str, Any]],
) -> list[dict[str, Any]]:
    """Convert database tool configs to OpenAI chat completion tool format (for acompletion()).

    Args:
        tools: List of tool configs from database (objects or dicts)

    Returns:
        List of OpenAI chat completion tool format dictionaries (ChatCompletionToolParam)
    """
    openai_tools: list[dict[str, Any]] = []

    for tool in tools:
        name = _get_tool_attr(tool, "name")
        active = _get_tool_attr(tool, "active", True)
        if not name or not active:
            continue

        # Build properties from arguments JSONB
        properties: dict[str, Any] = {}
        required_fields: list[str] = []

        arguments = _get_tool_attr(tool, "arguments") or {}
        argument_descriptions = _get_tool_attr(tool, "argument_descriptions") or {}

        if isinstance(arguments, dict):
            for field_name, field_spec in arguments.items():
                if not isinstance(field_spec, dict):
                    continue

                field_type = field_spec.get("type", "string")
                field_required = bool(field_spec.get("required", False))
                field_description = argument_descriptions.get(field_name, "")

                if field_type == "array":
                    items = field_spec.get("items") or {}
                    item_type = (
                        items.get("type", "string")
                        if isinstance(items, dict)
                        else "string"
                    )
                    properties[field_name] = {
                        "type": "array",
                        "items": {"type": item_type},
                        "description": field_description,
                    }
                elif field_type == "object":
                    properties[field_name] = {
                        "type": "object",
                        "description": field_description,
                    }
                else:
                    # map primitives
                    json_type = (
                        field_type
                        if field_type in ("string", "integer", "number", "boolean")
                        else "string"
                    )
                    properties[field_name] = {
                        "type": json_type,
                        "description": field_description,
                    }

                if field_required:
                    required_fields.append(field_name)

        openai_tools.append(
            {
                "type": "function",
                "function": {
                    "name": name,
                    "description": _get_tool_attr(tool, "description") or "",
                    "parameters": {
                        "type": "object",
                        "properties": properties,
                        "required": required_fields,
                    },
                },
            }
        )

    return openai_tools


def convert_tools_to_responses_format(
    tools: list[IGetTextRunContextAndCreateRunV4Tool] | list[dict[str, Any]],
) -> list[FunctionToolParam]:
    """Convert database tool configs to Responses API tool format (for aresponses()).

    Args:
        tools: List of tool configs from database (objects or dicts)

    Returns:
        List of FunctionToolParam dictionaries (for Responses API)
    """
    responses_tools: list[FunctionToolParam] = []

    for tool in tools:
        name = _get_tool_attr(tool, "name")
        active = _get_tool_attr(tool, "active", True)
        if not name or not active:
            continue

        # Build parameters from arguments JSONB
        parameters: dict[str, Any] = {}
        required_fields: list[str] = []

        arguments = _get_tool_attr(tool, "arguments") or {}
        argument_descriptions = _get_tool_attr(tool, "argument_descriptions") or {}

        if isinstance(arguments, dict):
            for field_name, field_spec in arguments.items():
                if not isinstance(field_spec, dict):
                    continue

                field_type = field_spec.get("type", "string")
                field_description = argument_descriptions.get(field_name, "")

                if field_type == "array":
                    items = field_spec.get("items") or {}
                    item_type = (
                        items.get("type", "string")
                        if isinstance(items, dict)
                        else "string"
                    )
                    parameters[field_name] = {
                        "type": "array",
                        "items": {"type": item_type},
                        "description": field_description,
                    }
                elif field_type == "object":
                    parameters[field_name] = {
                        "type": "object",
                        "description": field_description,
                    }
                else:
                    # map primitives
                    json_type = (
                        field_type
                        if field_type in ("string", "integer", "number", "boolean")
                        else "string"
                    )
                    parameters[field_name] = {
                        "type": json_type,
                        "description": field_description,
                    }

                # When strict=True, ALL properties must be in the required array
                # OpenAI enforces this: "required is required to be supplied and to be
                # an array including every key in properties"
                required_fields.append(field_name)

        # Responses API format: FunctionToolParam (flat structure, not nested)
        # When strict=True, additionalProperties must be explicitly set to false
        responses_tools.append(
            {
                "type": "function",
                "name": name,
                "description": _get_tool_attr(tool, "description") or "",
                "parameters": {
                    "type": "object",
                    "properties": parameters,
                    "required": required_fields,
                    "additionalProperties": False,  # Required when strict=True
                },
                "strict": True,  # Default to strict validation
            }
        )

    return responses_tools
