"""Build tool functions dynamically from database tool configs."""

from collections.abc import Callable
from typing import Any

from pydantic import Field
from utils.logging.db_logger import get_logger

from app.infra.tools.build_pydantic_fields import build_function_signature_string

logger = get_logger(__name__)


def build_tool_from_config(tool_config: dict[str, Any]) -> Callable[..., Any]:
    """Build a tool function from a database tool config.

    Args:
        tool_config: Tool config dict from database with keys:
            - name: Tool name (str)
            - description: Tool description (str) - used as function docstring
            - arguments: JSONB schema with types and required flags
            - argument_descriptions: JSONB with field descriptions
            - argument_defaults: JSONB with default values

    Returns:
        An async function ready to use for tool calling

    Example:
        >>> tool_config = {
        ...     "name": "create_template",  # create_title was dropped
        ...     "description": "Create a descriptive title for this content item.",
        ...     "arguments": {"title": {"type": "string", "required": True}},
        ...     "argument_descriptions": {"title": "A descriptive title"},
        ...     "argument_defaults": {}
        ... }
        >>> tool = build_tool_from_config(tool_config)
    """
    tool_name = tool_config.get("name", "")
    tool_description = tool_config.get("description", "")
    if not tool_name:
        raise ValueError("Tool config must have a 'name' field")
    if not tool_description:
        logger.warning(f"Tool {tool_name} has no description, using default")
        tool_description = f"Tool {tool_name}"

    # Build function signature string
    signature_str, param_names = build_function_signature_string(tool_config)

    # Generate return message from tool name
    # Convert snake_case to Title Case for return message
    return_message = _generate_return_message(tool_name, tool_description)

    # Build function code
    # Use param_names to create the function body that returns the success message
    # For simple tools, we just return a success message
    # SQL handles persistence via tool_call_arguments table
    func_body = f'    """{tool_description}"""\n'
    func_body += "    # SQL handles persistence via tool_call_arguments\n"
    func_body += f'    return "{return_message}"'

    # Build complete function code
    func_code = f"async def {tool_name}({signature_str}):\n{func_body}"

    # Create namespace for exec()
    import builtins

    exec_namespace = {
        "__builtins__": builtins,
        "Field": Field,
        "str": str,
        "int": int,
        "float": float,
        "bool": bool,
        "list": list,
        "dict": dict,
        "Any": Any,
    }

    # Execute function code
    try:
        exec(func_code, exec_namespace, exec_namespace)
        tool_func = exec_namespace[tool_name]
    except Exception as e:
        logger.error(f"Failed to build tool {tool_name}: {e}")
        raise ValueError(f"Failed to build tool {tool_name}: {e}") from e

    # Return the function directly (no wrapper needed - tools are simple)
    return tool_func


def _generate_return_message(tool_name: str, tool_description: str) -> str:
    """Generate an appropriate return message for a tool.

    Args:
        tool_name: Name of the tool (e.g., "create_title")
        tool_description: Description of the tool

    Returns:
        A success message string
    """
    # Convert snake_case to readable format
    # "create_title" -> "Created title successfully"  # Tool was dropped
    # "create_html" -> "Generated template HTML successfully"
    # "create_schema" -> "Generated template schema successfully"

    # Handle common patterns
    if tool_name.startswith("create_"):
        item = tool_name.replace("create_", "").replace("_", " ")
        return f"Created {item} successfully"
    elif tool_name.startswith("generate_"):
        item = tool_name.replace("generate_", "").replace("_", " ")
        return f"Generated {item} successfully"
    elif tool_name.startswith("set_"):
        item = tool_name.replace("set_", "").replace("_", " ")
        return f"Set {item} successfully"
    else:
        # Fallback: use description or tool name
        # Extract first verb + noun from description if possible
        words = tool_description.lower().split()
        if len(words) >= 2:
            verb = words[0]
            noun = " ".join(words[1:3]) if len(words) > 2 else words[1]
            # Convert to past tense
            if verb == "create":
                verb = "Created"
            elif verb == "generate":
                verb = "Generated"
            elif verb == "set":
                verb = "Set"
            else:
                verb = verb.capitalize()
            return f"{verb} {noun} successfully"
        else:
            return f"Tool {tool_name} completed successfully"
