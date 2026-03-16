"""Dynamic discovery helpers for artifact generation workflow.

This module provides functions to dynamically discover:
- SQL function names for resource creation
- Table column structures for resources
- Schema field mappings
- Agent end event names

All discovery is database-driven, eliminating the need for hardcoded mappings.
"""

import re
from typing import Any

import asyncpg


async def get_resource_sql_function_name(
    conn: asyncpg.Connection, resource_type: str
) -> str | None:
    """Discover SQL function name for creating a resource type.

    Queries pg_proc for functions matching pattern:
    - api_create_{resource_type}_v4
    - api_create_{resource_type}s_v4 (pluralized)

    Args:
        conn: Database connection
        resource_type: Resource type name (e.g., "personas", "names")

    Returns:
        Function name if found, None otherwise
    """
    # Try singular form first
    singular = f"api_create_{resource_type}_v4"
    found = await conn.fetchval(
        """
        SELECT 1 FROM pg_proc p
        JOIN pg_namespace n ON n.oid = p.pronamespace
        WHERE n.nspname = 'public' AND p.proname = $1
        """,
        singular,
    )
    if found:
        return singular

    # Try plural form
    plural = f"api_create_{resource_type}s_v4"
    found = await conn.fetchval(
        """
        SELECT 1 FROM pg_proc p
        JOIN pg_namespace n ON n.oid = p.pronamespace
        WHERE n.nspname = 'public' AND p.proname = $1
        """,
        plural,
    )
    if found:
        return plural

    return None


async def get_resource_table_columns(
    conn: asyncpg.Connection, resource_type: str
) -> list[dict[str, Any]]:
    """Discover table columns for a resource type.

    Queries information_schema.columns to get all columns for the resource table.
    Filters out system columns (id, created_at) as these are handled
    automatically by the database.

    Args:
        conn: Database connection
        resource_type: Resource type name (e.g., "personas", "names")

    Returns:
        List of column metadata dictionaries
    """
    rows = await conn.fetch(
        """
        SELECT
            column_name::text as name,
            data_type::text as data_type,
            (is_nullable = 'YES') as is_nullable,
            column_default::text as column_default
        FROM information_schema.columns
        WHERE table_schema = 'public'
          AND table_name = $1 || '_resource'
          AND column_name NOT IN ('id', 'created_at')
        ORDER BY ordinal_position
        """,
        resource_type,
    )

    return [
        {
            "name": str(row["name"]),
            "data_type": str(row["data_type"]),
            "is_nullable": bool(row["is_nullable"]),
            "column_default": str(row["column_default"])
            if row["column_default"]
            else None,
        }
        for row in rows
    ]


async def get_entry_table_columns(
    conn: asyncpg.Connection, entry_type: str
) -> list[dict[str, Any]]:
    """Discover table columns for an entry type.

    Queries information_schema.columns to get all columns for the entry table.
    Filters out system columns (id, created_at, updated_at).

    Args:
        conn: Database connection
        entry_type: Entry type name (e.g., "contents", "hints")

    Returns:
        List of column metadata dictionaries
    """
    table_name = f"{entry_type}_entry"
    rows = await conn.fetch(
        """
        SELECT
            column_name::text as name,
            data_type::text as data_type,
            (is_nullable = 'YES') as is_nullable,
            column_default::text as column_default
        FROM information_schema.columns
        WHERE table_schema = 'public'
          AND table_name = $1
          AND column_name NOT IN ('id', 'created_at', 'updated_at')
        ORDER BY ordinal_position
        """,
        table_name,
    )

    return [
        {
            "name": str(row["name"]),
            "data_type": str(row["data_type"]),
            "is_nullable": bool(row["is_nullable"]),
            "column_default": str(row["column_default"])
            if row["column_default"]
            else None,
        }
        for row in rows
    ]


def get_resource_schema_fields(resource_type: str) -> list[dict[str, Any]]:
    """Get output schema fields for a resource type from the registry."""
    from app.registry.resource_output_schemas import RESOURCE_OUTPUT_SCHEMAS

    return [
        {
            "name": f["name"],
            "field_type": f["field_type"],
            "required": False,
            "position": 0,
            "template": "",
        }
        for f in RESOURCE_OUTPUT_SCHEMAS.get(resource_type, [])
    ]


async def get_resource_output_schema_fields(
    conn: asyncpg.Connection, tool_id: str
) -> list[dict[str, Any]]:
    """Get output schema fields for a tool via tools_resource → args_outputs_resource.

    Used to map template_values (which use output schema field names)
    to table column names.
    """
    import uuid

    tool_uuid = uuid.UUID(tool_id)
    rows = await conn.fetch(
        """
        SELECT
            ao.name::text as name,
            'string'::text as field_type,
            false as required,
            0 as position,
            COALESCE(ao.template, '')::text as template
        FROM tools_resource tr
        JOIN LATERAL unnest(tr.args_output_ids) AS aoid(id) ON true
        JOIN args_outputs_resource ao ON ao.id = aoid.id AND ao.active = true
        WHERE tr.id = $1
          AND tr.active = true
        ORDER BY ao.created_at
        """,
        tool_uuid,
    )

    return [
        {
            "name": str(row["name"]),
            "field_type": str(row["field_type"]),
            "required": bool(row["required"]),
            "position": int(row["position"]),
            "template": str(row["template"]),
        }
        for row in rows
    ]


def extract_template_variable_name(template: str) -> str | None:
    """Extract variable name from Jinja template.

    Extracts the first variable name from templates like:
    - {{ message }} -> "message"
    - {{ variable.property }} -> "variable"
    - {{ variable|filter }} -> "variable"
    """
    if not template or not template.strip():
        return None

    match = re.search(r"\{\{\s*([a-zA-Z_][a-zA-Z0-9_]*)", template)
    if match:
        return match.group(1)

    return None


async def map_template_values_to_table_columns(
    conn: asyncpg.Connection,
    resource_type: str,
    template_values: dict[str, Any],
    tool_id: str | None = None,
    is_entry: bool = False,
) -> dict[str, Any]:
    """Map template values (using schema field names) to table column names."""
    # Get table columns (handle both resource and entry tables)
    if is_entry:
        table_columns = await get_entry_table_columns(conn, resource_type)
    else:
        table_columns = await get_resource_table_columns(conn, resource_type)
    column_names = {col["name"] for col in table_columns}

    # Get output schema fields (either from tool_id or resource_schemas)
    if tool_id:
        schema_fields = await get_resource_output_schema_fields(conn, tool_id)
    else:
        schema_fields = get_resource_schema_fields(resource_type)

    # Build mapping: schema field name -> table column name
    mapped_data: dict[str, Any] = {}

    for schema_field in schema_fields:
        schema_field_name = schema_field["name"]
        template = schema_field.get("template", "")

        # Try direct match first
        if schema_field_name in column_names:
            if schema_field_name in template_values:
                mapped_data[schema_field_name] = template_values[schema_field_name]
            continue

        # Try extracting variable name from template
        var_name = extract_template_variable_name(template)
        if var_name and var_name in column_names:
            if schema_field_name in template_values:
                mapped_data[var_name] = template_values[schema_field_name]
            continue

        # Fallback: use schema field name (may not match, but worth trying)
        if schema_field_name in template_values:
            mapped_data[schema_field_name] = template_values[schema_field_name]

    return mapped_data


async def get_agent_end_event_name(conn: asyncpg.Connection, artifact_type: str) -> str:
    """Discover agent end event name for an artifact type.

    Checks if artifact_type is a valid value in the artifacts enum.
    If found, returns {artifact_type}_end. Otherwise returns "text_end" as default.
    """
    # Check if artifact_type is a valid enum value
    found = await conn.fetchval(
        """
        SELECT 1 FROM unnest(enum_range(NULL::artifact_type)) AS e
        WHERE e::text = $1
        """,
        artifact_type,
    )
    if found:
        return f"{artifact_type}_end"

    # Special case: audio maps to voice
    if artifact_type == "audio":
        return "voice_end"

    return "text_end"
