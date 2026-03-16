"""Render tool templates using Jinja2 to map tool arguments to schema output fields."""

import uuid
from typing import Any

import asyncpg
from jinja2 import Environment, TemplateError, TemplateSyntaxError
from jinja2.environment import Template as JinjaTemplate
from redis.asyncio import Redis

from app.tools.resources.args_outputs.get import get_args_outputs
from app.tools.resources.tools.get import get_tools
from app.utils.logging.db_logger import get_logger

logger = get_logger(__name__)


def validate_jinja_template(template_expr: str) -> tuple[bool, str | None]:
    """Validate Jinja template syntax.

    Returns:
        Tuple of (is_valid, error_message)
    """
    if not template_expr or template_expr.strip() == "":
        return True, None

    try:
        env = Environment(
            autoescape=True,
            trim_blocks=True,
            lstrip_blocks=True,
        )
        env.parse(template_expr)
        return True, None
    except TemplateSyntaxError as e:
        return False, f"Template syntax error: {str(e)}"
    except Exception as e:
        return False, f"Template validation error: {str(e)}"


async def render_tool_template(
    conn: asyncpg.Connection,
    tool_id: uuid.UUID,
    tool_arguments: dict[str, Any],
    redis: Redis | None = None,
) -> dict[str, Any]:
    """Render Jinja templates for a tool's output schema fields using tool arguments.

    Composes get_tools + get_args_outputs black boxes — no inline SQL.
    """
    # Step 1: Get tool resource to find args_output_ids
    if not redis:
        from app.infra.globals import get_redis_client

        redis = get_redis_client()

    tools = await get_tools(conn, [tool_id], redis)
    if not tools:
        logger.warning(f"Tool {tool_id} not found, skipping template rendering")
        return {}

    args_output_ids = tools[0].args_output_ids or []
    if not args_output_ids:
        logger.warning(
            f"Tool {tool_id} has no output schema fields, skipping template rendering"
        )
        return {}

    # Step 2: Get args_outputs resources
    args_outputs = await get_args_outputs(conn, args_output_ids, redis)
    if not args_outputs:
        logger.warning(
            f"Tool {tool_id} has no output schema fields, skipping template rendering"
        )
        return {}

    schema_fields = [
        {"name": ao.name, "template": ao.template}
        for ao in args_outputs
        if ao.name and ao.active
    ]

    # Create Jinja2 environment with autoescape enabled for security
    env = Environment(
        autoescape=True,
        trim_blocks=True,
        lstrip_blocks=True,
    )

    # Render each template
    rendered_values: dict[str, Any] = {}

    for field in schema_fields:
        field_name = field["name"]
        template_expr = field["template"]

        # Skip empty templates (no transformation needed)
        if not template_expr or template_expr.strip() == "":
            continue

        try:
            template: JinjaTemplate = env.from_string(template_expr)
            rendered_value = template.render(**tool_arguments)
            rendered_values[field_name] = str(rendered_value)

            logger.debug(
                f"Rendered template for field '{field_name}': '{template_expr}' -> '{rendered_value}'"
            )

        except TemplateError as e:
            logger.error(
                f"Jinja template error for field '{field_name}' with template '{template_expr}': {str(e)}"
            )
            continue
        except Exception as e:
            logger.error(
                f"Unexpected error rendering template for field '{field_name}': {str(e)}"
            )
            continue

    logger.info(f"Rendered {len(rendered_values)} fields for tool {tool_id}")

    return rendered_values


async def get_rendered_template_values(
    conn: asyncpg.Connection,
    tool_call_id: uuid.UUID,
) -> dict[str, Any] | None:
    """Get rendered template values from tool_call_results for a tool call.

    Note: The underlying SQL function is a stub that always returns None.
    """
    return None
