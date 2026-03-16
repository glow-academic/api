"""Build Pydantic Field definitions from tool config."""

from typing import Any

from pydantic import Field

from app.utils.logging.db_logger import get_logger

logger = get_logger(__name__)


def build_pydantic_fields(tool_config: dict[str, Any]) -> dict[str, Any]:
    """Convert tool config from database into Pydantic Field definitions.

    Args:
        tool_config: Tool config dict with 'arguments', 'argument_descriptions',
                    'argument_defaults' keys (all JSONB)

    Returns:
        Dict mapping field names to Pydantic Field definitions for use in function signature
    """
    arguments = tool_config.get("arguments", {})
    argument_descriptions = tool_config.get("argument_descriptions", {})
    argument_defaults = tool_config.get("argument_defaults", {})

    fields: dict[str, Any] = {}

    for field_name, field_spec in arguments.items():
        if not isinstance(field_spec, dict):
            logger.warning(f"Invalid field spec for {field_name}: {field_spec}")
            continue

        field_type = field_spec.get("type", "string")
        required = field_spec.get("required", True)
        description = argument_descriptions.get(field_name, "")
        default_value = argument_defaults.get(field_name)

        # Map database types to Python types
        python_type: type
        if field_type == "string":
            python_type = str
        elif field_type == "integer":
            python_type = int
        elif field_type == "number":
            python_type = float
        elif field_type == "boolean":
            python_type = bool
        elif field_type == "array":
            # Check if items type is specified
            items_type = field_spec.get("items", {}).get("type", "string")
            if items_type == "string":
                python_type = list[str]
            elif items_type == "integer":
                python_type = list[int]
            elif items_type == "number":
                python_type = list[float]
            else:
                python_type = list[Any]  # type: ignore[assignment]
        elif field_type == "object":
            python_type = dict[str, Any]  # type: ignore[assignment]
        else:
            logger.warning(
                f"Unknown field type {field_type} for {field_name}, defaulting to str"
            )
            python_type = str

        # Build Field definition
        if required and default_value is None:
            # Required field with no default
            fields[field_name] = Field(..., description=description)
        elif required and default_value is not None:
            # Required field with default (shouldn't happen, but handle it)
            fields[field_name] = Field(default=default_value, description=description)
        else:
            # Optional field
            if default_value is not None:
                fields[field_name] = Field(
                    default=default_value, description=description
                )
            else:
                # Optional with no default - use None
                fields[field_name] = Field(default=None, description=description)

    return fields


def build_function_signature_string(
    tool_config: dict[str, Any],
) -> tuple[str, list[str]]:
    """Build function signature string from tool config for use with exec().

    Args:
        tool_config: Tool config dict with 'arguments', 'argument_descriptions',
                    'argument_defaults' keys (all JSONB)

    Returns:
        Tuple of (signature_string, param_names) for building function with exec()
    """
    arguments = tool_config.get("arguments", {})
    argument_descriptions = tool_config.get("argument_descriptions", {})
    argument_defaults = tool_config.get("argument_defaults", {})

    param_definitions = []
    param_names = []

    for field_name, field_spec in arguments.items():
        if not isinstance(field_spec, dict):
            continue

        field_type = field_spec.get("type", "string")
        required = field_spec.get("required", True)
        description = argument_descriptions.get(field_name, "")
        default_value = argument_defaults.get(field_name)

        # Map database types to Python type strings
        python_type_str = "str"
        if field_type == "integer":
            python_type_str = "int"
        elif field_type == "number":
            python_type_str = "float"
        elif field_type == "boolean":
            python_type_str = "bool"
        elif field_type == "array":
            items_type = field_spec.get("items", {}).get("type", "string")
            if items_type == "string":
                python_type_str = "list[str]"
            elif items_type == "integer":
                python_type_str = "list[int]"
            elif items_type == "number":
                python_type_str = "list[float]"
            else:
                python_type_str = "list[Any]"
        elif field_type == "object":
            python_type_str = "dict[str, Any]"

        param_names.append(field_name)

        # Build Field annotation string
        if required and default_value is None:
            param_def = f"{field_name}: {python_type_str} = Field(..., description={repr(description)})"
        elif required and default_value is not None:
            param_def = f"{field_name}: {python_type_str} = Field(default={repr(default_value)}, description={repr(description)})"
        else:
            if default_value is not None:
                param_def = f"{field_name}: {python_type_str} | None = Field(default={repr(default_value)}, description={repr(description)})"
            else:
                param_def = f"{field_name}: {python_type_str} | None = Field(default=None, description={repr(description)})"

        param_definitions.append(param_def)

    signature_str = ", ".join(param_definitions)
    return signature_str, param_names
