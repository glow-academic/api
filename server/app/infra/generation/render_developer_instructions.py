"""Render developer instruction templates with Jinja context.

Shared utility for rendering developer instruction templates with whitelisted
resource context. Used by persona/generate.py and other resource handlers.
"""

import json
from typing import Any

from jinja2 import Environment, TemplateError

from app.utils.logging.db_logger import get_logger

logger = get_logger(__name__)


def render_developer_instructions(
    templates: list[str] | None,
    jinja_context: dict[str, Any] | str | None,
) -> list[str]:
    """Render Jinja templates with context.

    Args:
        templates: List of Jinja template strings (raw developer instructions)
        jinja_context: Dictionary of whitelisted resources for templating,
                      or JSON string that will be parsed

    Returns:
        List of rendered instruction strings (empty strings and failed renders filtered out)

    Example:
        >>> templates = [
        ...     "Generate names for: {{ names | join(', ') }}",
        ...     "Use colors: {% for c in colors %}{{ c.name }}{% endfor %}"
        ... ]
        >>> context = {
        ...     "names": [{"id": "1", "name": "Alice"}],
        ...     "colors": [{"id": "2", "name": "Blue", "hex_code": "#0000FF"}]
        ... }
        >>> rendered = render_developer_instructions(templates, context)
    """
    if not templates:
        return []

    # Parse context if it's a JSON string
    context_dict: dict[str, Any] = {}
    if jinja_context:
        if isinstance(jinja_context, str):
            try:
                parsed = json.loads(jinja_context)
                context_dict = parsed if isinstance(parsed, dict) else {}
            except (json.JSONDecodeError, TypeError):
                logger.warning(
                    "Failed to parse jinja_context as JSON, using empty context"
                )
                context_dict = {}
        elif isinstance(jinja_context, dict):
            context_dict = jinja_context
        else:
            logger.warning(
                f"Unexpected jinja_context type: {type(jinja_context)}, using empty context"
            )
            context_dict = {}

    # Create Jinja environment with security settings
    env = Environment(
        autoescape=True,
        trim_blocks=True,
        lstrip_blocks=True,
    )

    rendered: list[str] = []

    for template_str in templates:
        if not template_str or not template_str.strip():
            continue

        try:
            template = env.from_string(template_str)
            content = template.render(**context_dict)

            if content and content.strip():
                rendered.append(content.strip())
        except TemplateError as e:
            logger.warning(f"Failed to render developer instruction template: {str(e)}")
            continue
        except Exception as e:
            logger.warning(f"Unexpected error rendering template: {str(e)}")
            continue

    return rendered


def convert_tools_to_dict(
    tools: list[Any] | None,
) -> list[dict[str, Any]] | None:
    """Convert tool objects to dictionaries for JSON serialization.

    Args:
        tools: List of tool objects (from SQL query result)

    Returns:
        List of tool dictionaries suitable for JSON serialization
    """
    if not tools:
        return None

    result: list[dict[str, Any]] = []

    for tool in tools:
        if tool is None:
            continue

        # Handle different tool formats
        tool_dict: dict[str, Any] = {}

        if hasattr(tool, "_asdict"):
            # Named tuple from asyncpg
            tool_dict = dict(tool._asdict())
        elif hasattr(tool, "model_dump"):
            # Pydantic model
            tool_dict = tool.model_dump()
        elif hasattr(tool, "dict"):
            # Pydantic v1
            tool_dict = tool.dict()
        elif isinstance(tool, dict):
            tool_dict = tool
        elif isinstance(tool, tuple):
            # Raw tuple - map to expected fields
            # (id, name, description, resource, artifact, arguments, argument_descriptions, argument_defaults, active)
            if len(tool) >= 9:
                tool_dict = {
                    "id": str(tool[0]) if tool[0] else None,
                    "name": tool[1],
                    "description": tool[2],
                    "resource": tool[3],
                    "artifact": tool[4],
                    "arguments": tool[5] if isinstance(tool[5], dict) else {},
                    "argument_descriptions": tool[6]
                    if isinstance(tool[6], dict)
                    else {},
                    "argument_defaults": tool[7] if isinstance(tool[7], dict) else {},
                    "active": tool[8] if len(tool) > 8 else True,
                }
        else:
            logger.warning(f"Unknown tool format: {type(tool)}")
            continue

        # Only include active tools with names
        if tool_dict.get("name") and tool_dict.get("active", True):
            result.append(tool_dict)

    return result if result else None
