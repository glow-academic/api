#!/usr/bin/env python3
"""Validate tool templates and schemas.

This script audits:
1. All resources in the resources enum
2. Which resources have tools
3. Tool structure validation (template_id chains, schemas)
4. Jinja template validation (syntax and variable references)
5. Output schema vs database table validation
6. Agent existence per artifact (Category 4)
7. Prompt/instruction schema validation (Category 5)
8. Enhanced output mapping validation - CREATE operations (Category 3)
"""

import os
import re
import sys
from collections import defaultdict
from pathlib import Path
from typing import Any

import asyncpg  # type: ignore
from jinja2 import Environment, TemplateSyntaxError

# Add server directory to path for imports
server_dir = Path(__file__).parent.parent
sys.path.insert(0, str(server_dir))

# Jinja2 environment for validation
jinja_env = Environment(autoescape=True, trim_blocks=True, lstrip_blocks=True)


def extract_jinja_variables(template: str) -> set[str]:
    """Extract variable names from Jinja template.

    Args:
        template: Jinja template string

    Returns:
        Set of variable names (base names before . or |)
    """
    if not template or not template.strip():
        return set()

    # Pattern to match {{ variable }} or {{ variable.property }} or {{ variable|filter }}
    pattern = r"\{\{\s*([a-zA-Z_][a-zA-Z0-9_]*)"
    matches = re.findall(pattern, template)

    # Extract base variable names (before first . or |)
    variables = set()
    for match in matches:
        # Remove any filters or properties
        base_name = match.split(".")[0].split("|")[0].strip()
        if base_name:
            variables.add(base_name)

    return variables


def validate_jinja_syntax(template: str) -> tuple[bool, str | None]:
    """Validate Jinja template syntax.

    Args:
        template: Jinja template string

    Returns:
        Tuple of (is_valid, error_message)
    """
    if not template or not template.strip():
        return True, None

    try:
        jinja_env.parse(template)
        return True, None
    except TemplateSyntaxError as e:
        return False, str(e)
    except Exception as e:
        return False, f"Template validation error: {str(e)}"


async def run_audit(conn: asyncpg.Connection) -> dict[str, Any]:
    """Run comprehensive audit of tools and templates.

    Args:
        conn: Database connection

    Returns:
        Dictionary with audit results
    """
    results: dict[str, Any] = {
        "resources": [],
        "resources_with_tools": [],
        "resources_missing_tools": [],
        "tools": [],
        "tools_missing_output_schema": [],
        "tools_missing_input_schema": [],
        "jinja_validation_errors": [],
        "schema_table_mismatches": [],
        "resources_missing_tables": [],
        "output_mapping_gaps": [],
        "granular_schema_validation": [],
        "insert_column_coverage": [],
        "data_type_compatibility": [],
        "artifacts_missing_agents": [],
        "agents_missing_tools": [],
        "agents_missing_prompts": [],
        "agents_missing_instructions": [],
        "statistics": {},
    }

    # Query 1: All resources
    resources = await conn.fetch("""
        SELECT enumlabel::text as resource
        FROM pg_enum 
        WHERE enumtypid = (SELECT oid FROM pg_type WHERE typname = 'resources')
        ORDER BY enumlabel
    """)
    results["resources"] = [r["resource"] for r in resources]

    # Query 2: Resources with tools
    resources_with_tools = await conn.fetch("""
        SELECT 
            rt.resource::text,
            COUNT(DISTINCT rt.tool_id) as tool_count,
            string_agg(DISTINCT tool_n.name, ', ' ORDER BY tool_n.name) as tool_names
        FROM resource_tools_relation rt
        JOIN tool_artifact t ON t.id = rt.tool_id
        JOIN tool_flags tf ON tf.tool_id = t.id
        JOIN flags_resource f ON tf.flag_id = f.id
        LEFT JOIN tool_names tn ON tn.tool_id = t.id AND tn.active = true
        LEFT JOIN names_resource tool_n ON tool_n.id = tn.name_id
        WHERE f.name = 'active' AND tf.type = 'active'::type_tool_flags AND tf.value = true
        AND rt.active = true
        GROUP BY rt.resource
        ORDER BY rt.resource
    """)
    results["resources_with_tools"] = [
        {
            "resource": r["resource"],
            "tool_count": r["tool_count"],
            "tool_names": r["tool_names"],
        }
        for r in resources_with_tools
    ]

    # Query 3: Resources missing tools
    resources_missing_tools = await conn.fetch("""
        SELECT enumlabel::text as resource
        FROM pg_enum 
        WHERE enumtypid = (SELECT oid FROM pg_type WHERE typname = 'resources')
        AND enumlabel::text NOT IN (
            SELECT DISTINCT resource::text 
            FROM resource_tools_relation
        )
        ORDER BY enumlabel
    """)
    results["resources_missing_tools"] = [
        r["resource"] for r in resources_missing_tools
    ]

    # Query 4: Tool structure
    tools = await conn.fetch("""
        SELECT 
            t.id as tool_id,
            tool_n.name as tool_name,
            tt.template_id,
            rt.resource::text as resource,
            CASE WHEN ts.schema_id IS NOT NULL THEN true ELSE false END as has_input_schema,
            ts.schema_id as input_schema_id,
            CASE WHEN st.schema_id IS NOT NULL THEN true ELSE false END as has_output_schema,
            st.schema_id as output_schema_id,
            CASE WHEN tmpl.id IS NOT NULL THEN true ELSE false END as template_exists,
            (SELECT COUNT(*) FROM schema_fields_resource WHERE schema_id = ts.schema_id AND active = true) as input_field_count,
            (SELECT COUNT(*) FROM schema_fields_resource WHERE schema_id = st.schema_id AND active = true) as output_field_count
        FROM tool_artifact t
        JOIN tool_flags tf ON tf.tool_id = t.id
        JOIN flags_resource f ON tf.flag_id = f.id
        LEFT JOIN tool_names tn ON tn.tool_id = t.id AND tn.active = true
        LEFT JOIN names_resource tool_n ON tool_n.id = tn.name_id
        LEFT JOIN resource_tools_relation rt ON rt.tool_id = t.id
        LEFT JOIN tool_schemas ts ON ts.tool_id = t.id
        LEFT JOIN tool_templates tt ON tt.tool_id = t.id AND tt.type = 'output'::type_tool_templates
        LEFT JOIN schema_templates st ON st.template_id = tt.template_id
        LEFT JOIN templates_resource tmpl ON tmpl.id = tt.template_id
        WHERE f.name = 'active' AND tf.type = 'active'::type_tool_flags AND tf.value = true
        ORDER BY tool_n.name
    """)
    results["tools"] = [dict(r) for r in tools]

    # Query 5: Tools missing output schemas
    tools_missing_output = await conn.fetch("""
        SELECT 
            t.id as tool_id,
            tool_n.name as tool_name,
            tt.template_id,
            rt.resource::text as resource
        FROM tool_artifact t
        JOIN resource_tools_relation rt ON rt.tool_id = t.id
        JOIN tool_flags tf ON tf.tool_id = t.id
        JOIN flags_resource f ON tf.flag_id = f.id
        LEFT JOIN tool_names tn ON tn.tool_id = t.id AND tn.active = true
        LEFT JOIN names_resource tool_n ON tool_n.id = tn.name_id
        LEFT JOIN tool_templates tt ON tt.tool_id = t.id AND tt.type = 'output'::type_tool_templates
        LEFT JOIN schema_templates st ON st.template_id = tt.template_id
        WHERE f.name = 'active' AND tf.type = 'active'::type_tool_flags AND tf.value = true
        AND rt.active = true
        AND st.schema_id IS NULL
        ORDER BY tool_n.name
    """)
    results["tools_missing_output_schema"] = [dict(r) for r in tools_missing_output]

    # Query 6: Tools missing input schemas
    tools_missing_input = await conn.fetch("""
        SELECT 
            t.id as tool_id,
            tool_n.name as tool_name,
            rt.resource::text as resource
        FROM tool_artifact t
        JOIN resource_tools_relation rt ON rt.tool_id = t.id
        JOIN tool_flags tf ON tf.tool_id = t.id
        JOIN flags_resource f ON tf.flag_id = f.id
        LEFT JOIN tool_names tn ON tn.tool_id = t.id AND tn.active = true
        LEFT JOIN names_resource tool_n ON tool_n.id = tn.name_id
        LEFT JOIN tool_schemas ts ON ts.tool_id = t.id
        WHERE f.name = 'active' AND tf.type = 'active'::type_tool_flags AND tf.value = true
        AND rt.active = true
        AND ts.schema_id IS NULL
        ORDER BY tool_n.name
    """)
    results["tools_missing_input_schema"] = [dict(r) for r in tools_missing_input]

    # Query 7: Tool input arguments
    tool_arguments = await conn.fetch("""
        SELECT 
            t.id as tool_id,
            tool_n.name as tool_name,
            rt.resource::text as resource,
            sf.name as argument_name,
            sf.field_type as argument_type,
            sf.description as argument_description,
            sf.position
        FROM tool_artifact t
        JOIN resource_tools_relation rt ON rt.tool_id = t.id
        JOIN tool_flags tf ON tf.tool_id = t.id
        JOIN flags_resource f ON tf.flag_id = f.id
        LEFT JOIN tool_names tn ON tn.tool_id = t.id AND tn.active = true
        LEFT JOIN names_resource tool_n ON tool_n.id = tn.name_id
        LEFT JOIN tool_schemas ts ON ts.tool_id = t.id
        LEFT JOIN schema_fields_resource sf ON sf.schema_id = ts.schema_id AND sf.active = true
        WHERE f.name = 'active' AND tf.type = 'active'::type_tool_flags AND tf.value = true
        AND rt.active = true
        ORDER BY tool_n.name, sf.position NULLS LAST
    """)

    # Build tool arguments map
    tool_args_map: dict[str, set[str]] = defaultdict(set)
    for arg in tool_arguments:
        tool_name = arg["tool_name"]
        arg_name = arg["argument_name"]
        if arg_name:
            tool_args_map[tool_name].add(arg_name)

    # Query 8: Tool output schema fields with Jinja templates
    output_fields = await conn.fetch("""
        SELECT 
            t.id as tool_id,
            tool_n.name as tool_name,
            rt.resource::text as resource,
            sf.name as output_field_name,
            sf.field_type as output_field_type,
            sf.template as jinja_template,
            sf.position
        FROM tool_artifact t
        JOIN resource_tools_relation rt ON rt.tool_id = t.id
        JOIN tool_flags tf ON tf.tool_id = t.id
        JOIN flags_resource f ON tf.flag_id = f.id
        LEFT JOIN tool_names tn ON tn.tool_id = t.id AND tn.active = true
        LEFT JOIN names_resource tool_n ON tool_n.id = tn.name_id
        LEFT JOIN tool_templates tt ON tt.tool_id = t.id AND tt.type = 'output'::type_tool_templates
        LEFT JOIN schema_templates st ON st.template_id = tt.template_id
        LEFT JOIN schema_fields_resource sf ON sf.schema_id = st.schema_id AND sf.active = true
        WHERE f.name = 'active' AND tf.type = 'active'::type_tool_flags AND tf.value = true
        AND rt.active = true
        ORDER BY tool_n.name, sf.position NULLS LAST
    """)

    # Validate Jinja templates
    jinja_errors = []
    for field in output_fields:
        tool_name = field["tool_name"]
        output_field = field["output_field_name"]
        template = field["jinja_template"]

        if not template or not template.strip():
            continue

        # Validate syntax
        is_valid, error_msg = validate_jinja_syntax(template)
        if not is_valid:
            jinja_errors.append(
                {
                    "tool_name": tool_name,
                    "output_field": output_field,
                    "error": error_msg,
                    "template": template,
                }
            )
            continue

        # Extract variables and validate against tool arguments
        variables = extract_jinja_variables(template)
        available_args = tool_args_map.get(tool_name, set())

        for var in variables:
            if var not in available_args:
                jinja_errors.append(
                    {
                        "tool_name": tool_name,
                        "output_field": output_field,
                        "error": f"Template references unknown variable '{var}'",
                        "template": template,
                        "available_arguments": sorted(available_args),
                    }
                )

    results["jinja_validation_errors"] = jinja_errors

    # Query 9: Output schema fields vs database table columns (fixed to use _resource suffix)
    schema_table_checks = await conn.fetch("""
        SELECT 
            t.id as tool_id,
            tool_n.name as tool_name,
            rt.resource::text as resource,
            sf.name as schema_field_name,
            CASE 
                WHEN EXISTS (
                    SELECT 1 
                    FROM information_schema.columns 
                    WHERE table_schema = 'public' 
                    AND table_name = rt.resource::text || '_resource'
                    AND column_name = sf.name
                ) THEN true
                ELSE false
            END as field_exists_in_table,
            CASE 
                WHEN EXISTS (
                    SELECT 1 
                    FROM information_schema.tables 
                    WHERE table_schema = 'public' 
                    AND table_name = rt.resource::text || '_resource'
                ) THEN true
                ELSE false
            END as table_exists
        FROM tool_artifact t
        JOIN resource_tools_relation rt ON rt.tool_id = t.id
        JOIN tool_flags tf ON tf.tool_id = t.id
        JOIN flags_resource f ON tf.flag_id = f.id
        LEFT JOIN tool_names tn ON tn.tool_id = t.id AND tn.active = true
        LEFT JOIN names_resource tool_n ON tool_n.id = tn.name_id
        LEFT JOIN tool_templates tt ON tt.tool_id = t.id AND tt.type = 'output'::type_tool_templates
        LEFT JOIN schema_templates st ON st.template_id = tt.template_id
        LEFT JOIN schema_fields_resource sf ON sf.schema_id = st.schema_id AND sf.active = true
        WHERE f.name = 'active' AND tf.type = 'active'::type_tool_flags AND tf.value = true
        AND rt.active = true
        AND sf.name IS NOT NULL
        ORDER BY tool_n.name, sf.position
    """)

    schema_mismatches = []
    for check in schema_table_checks:
        if not check["table_exists"]:
            schema_mismatches.append(
                {
                    "tool_name": check["tool_name"],
                    "resource": check["resource"],
                    "schema_field": check["schema_field_name"],
                    "error": f"Table '{check['resource']}' does not exist",
                }
            )
        elif not check["field_exists_in_table"]:
            schema_mismatches.append(
                {
                    "tool_name": check["tool_name"],
                    "resource": check["resource"],
                    "schema_field": check["schema_field_name"],
                    "error": f"Field '{check['schema_field_name']}' does not exist in table '{check['resource']}'",
                }
            )

    results["schema_table_mismatches"] = schema_mismatches

    # Query 10: Resources without corresponding resource tables
    resources_missing_tables = await conn.fetch("""
        SELECT enumlabel::text as resource
        FROM pg_enum 
        WHERE enumtypid = (SELECT oid FROM pg_type WHERE typname = 'resources')
        AND enumlabel::text || '_resource' NOT IN (
            SELECT table_name 
            FROM information_schema.tables 
            WHERE table_schema = 'public' 
            AND table_type = 'BASE TABLE'
        )
        ORDER BY enumlabel
    """)
    results["resources_missing_tables"] = [
        r["resource"] for r in resources_missing_tables
    ]

    # Query 11: Output mapping gaps - required columns not covered by schemas
    output_mapping_gaps = await conn.fetch("""
        WITH resource_columns AS (
            SELECT 
                table_name,
                column_name,
                is_nullable,
                column_default,
                data_type
            FROM information_schema.columns
            WHERE table_schema = 'public'
            AND table_name LIKE '%_resource'
            AND column_name NOT IN ('id', 'created_at', 'updated_at')
        ),
        tool_output_fields AS (
            SELECT 
                rt.resource::text as resource,
                sf.name as output_field
            FROM tool_artifact t
            JOIN resource_tools_relation rt ON rt.tool_id = t.id
            JOIN tool_flags tf ON tf.tool_id = t.id
            JOIN flags_resource f ON tf.flag_id = f.id
            JOIN tool_templates tt ON tt.tool_id = t.id AND tt.type = 'output'::type_tool_templates
            JOIN schema_templates st ON st.template_id = tt.template_id
            JOIN schema_fields_resource sf ON sf.schema_id = st.schema_id AND sf.active = true
            WHERE f.name = 'active' AND tf.type = 'active'::type_tool_flags AND tf.value = true
            AND rt.active = true
        )
        SELECT 
            rc.table_name,
            rc.column_name,
            rc.is_nullable,
            rc.column_default,
            rc.data_type
        FROM resource_columns rc
        LEFT JOIN tool_output_fields tof ON 
            rc.table_name = tof.resource || '_resource' 
            AND rc.column_name = tof.output_field
        WHERE rc.is_nullable = 'NO' 
        AND rc.column_default IS NULL
        AND tof.output_field IS NULL
        ORDER BY rc.table_name, rc.column_name
    """)
    results["output_mapping_gaps"] = [dict(r) for r in output_mapping_gaps]

    # Query 12: Granular schema-table validation (data types, nullable, etc.)
    granular_validation = await conn.fetch("""
        WITH tool_output_schemas AS (
            SELECT 
                rt.resource::text as resource,
                tool_n.name as tool_name,
                sf.name as schema_field_name,
                sf.field_type::text as schema_field_type,
                sf.required as schema_required,
                sf.template as schema_template,
                sf.position as schema_position
            FROM tool_artifact t
            JOIN resource_tools_relation rt ON rt.tool_id = t.id
            JOIN tool_flags tf ON tf.tool_id = t.id
            JOIN flags_resource f ON tf.flag_id = f.id
            LEFT JOIN tool_names tn ON tn.tool_id = t.id AND tn.active = true
            LEFT JOIN names_resource tool_n ON tool_n.id = tn.name_id
            JOIN tool_templates tt ON tt.tool_id = t.id AND tt.type = 'output'::type_tool_templates
            JOIN schema_templates st ON st.template_id = tt.template_id
            JOIN schema_fields_resource sf ON sf.schema_id = st.schema_id AND sf.active = true
            WHERE f.name = 'active' AND tf.type = 'active'::type_tool_flags AND tf.value = true
            AND rt.active = true
        ),
        table_columns AS (
            SELECT 
                table_name,
                column_name,
                data_type,
                udt_name,
                is_nullable,
                column_default
            FROM information_schema.columns
            WHERE table_schema = 'public'
            AND table_name LIKE '%_resource'
        )
        SELECT 
            tos.resource,
            tos.tool_name,
            tos.schema_field_name,
            tos.schema_field_type,
            tos.schema_required,
            tos.schema_template,
            tc.column_name as table_column_name,
            tc.data_type as table_data_type,
            tc.udt_name as table_udt_name,
            tc.is_nullable as table_nullable,
            tc.column_default as table_default,
            CASE 
                WHEN tos.schema_field_type = 'string' AND tc.data_type IN ('text', 'character varying', 'character') THEN 'COMPATIBLE'
                WHEN tos.schema_field_type = 'string' AND tc.udt_name = 'uuid' THEN 'COMPATIBLE'
                WHEN tos.schema_field_type = 'number' AND tc.data_type IN ('integer', 'bigint', 'smallint') THEN 'COMPATIBLE'
                WHEN tos.schema_field_type = 'number' AND tc.data_type IN ('real', 'double precision', 'numeric') THEN 'COMPATIBLE'
                WHEN tos.schema_field_type = 'boolean' AND tc.data_type = 'boolean' THEN 'COMPATIBLE'
                WHEN tos.schema_field_type = 'array' AND tc.data_type LIKE '%[]' THEN 'COMPATIBLE'
                WHEN tos.schema_field_type = 'string' AND tc.data_type = 'jsonb' THEN 'COMPATIBLE'
                WHEN tc.column_name IS NULL THEN 'MISSING_COLUMN'
                ELSE 'TYPE_MISMATCH'
            END as type_compatibility,
            CASE 
                WHEN tc.column_name IS NULL THEN 'MISSING_COLUMN'
                WHEN tos.schema_required = true AND tc.is_nullable = 'NO' AND tc.column_default IS NULL THEN 'OK'
                WHEN tos.schema_required = true AND tc.is_nullable = 'YES' THEN 'WARNING: Schema required but column nullable'
                WHEN tos.schema_required = false AND tc.is_nullable = 'NO' AND tc.column_default IS NULL THEN 'WARNING: Schema optional but column NOT NULL'
                WHEN tos.schema_required = false AND (tc.is_nullable = 'YES' OR tc.column_default IS NOT NULL) THEN 'OK'
                ELSE 'OK'
            END as nullable_compatibility
        FROM tool_output_schemas tos
        LEFT JOIN table_columns tc ON 
            tc.table_name = tos.resource || '_resource'
            AND tc.column_name = tos.schema_field_name
        ORDER BY tos.resource, tos.schema_position
    """)
    results["granular_schema_validation"] = [dict(r) for r in granular_validation]

    # Query 13: INSERT column coverage analysis
    insert_coverage = await conn.fetch(r"""
        WITH function_inserts AS (
            SELECT 
                p.proname,
                regexp_replace(p.proname, 'api_create_', '') as resource_name,
                (regexp_match(pg_get_functiondef(p.oid), 'INSERT INTO (\w+_resource)\s*\(([^)]+)\)'))[2] as insert_columns_str
            FROM pg_proc p
            WHERE p.proname LIKE 'api_create_%_v4'
            AND p.pronamespace = (SELECT oid FROM pg_namespace WHERE nspname = 'public')
            AND pg_get_functiondef(p.oid) ~* 'INSERT INTO.*_resource\s*\('
        ),
        insert_columns_expanded AS (
            SELECT 
                proname,
                resource_name,
                trim(unnest(string_to_array(regexp_replace(insert_columns_str, '\s+', '', 'g'), ','))) as insert_column
            FROM function_inserts
            WHERE insert_columns_str IS NOT NULL
        ),
        system_managed_columns AS (
            SELECT unnest(ARRAY['id', 'created_at', 'updated_at', 'call_id', 'active', 'mcp', 'generated', 'group_id']) as column_name
        ),
        schema_fields_for_resource AS (
            SELECT 
                rt.resource::text as resource,
                tool_n.name as tool_name,
                sf.name as schema_field_name
            FROM tool_artifact t
            JOIN resource_tools_relation rt ON rt.tool_id = t.id
            JOIN tool_flags tf ON tf.tool_id = t.id
            JOIN flags_resource f ON tf.flag_id = f.id
            LEFT JOIN tool_names tn ON tn.tool_id = t.id AND tn.active = true
            LEFT JOIN names_resource tool_n ON tool_n.id = tn.name_id
            JOIN tool_templates tt ON tt.tool_id = t.id AND tt.type = 'output'::type_tool_templates
            JOIN schema_templates st ON st.template_id = tt.template_id
            JOIN schema_fields_resource sf ON sf.schema_id = st.schema_id AND sf.active = true
            WHERE f.name = 'active' AND tf.type = 'active'::type_tool_flags AND tf.value = true
            AND rt.active = true
        )
        SELECT 
            ice.proname,
            ice.resource_name,
            ice.insert_column,
            CASE 
                WHEN smc.column_name IS NOT NULL THEN 'SYSTEM_MANAGED'
                WHEN sfr.schema_field_name IS NOT NULL THEN 'COVERED_BY_SCHEMA'
                ELSE 'MISSING_FROM_SCHEMA'
            END as coverage_status,
            sfr.tool_name,
            sfr.schema_field_name
        FROM insert_columns_expanded ice
        LEFT JOIN system_managed_columns smc ON smc.column_name = ice.insert_column
        LEFT JOIN schema_fields_for_resource sfr ON 
            sfr.resource = ice.resource_name
            AND sfr.schema_field_name = ice.insert_column
        ORDER BY 
            CASE 
                WHEN smc.column_name IS NOT NULL THEN 3
                WHEN sfr.schema_field_name IS NOT NULL THEN 2
                ELSE 1
            END,
            ice.proname,
            ice.insert_column
    """)
    results["insert_column_coverage"] = [dict(r) for r in insert_coverage]

    # Query 14: Artifacts missing agents
    artifacts_missing_agents = await conn.fetch("""
        SELECT 
            a.artifact::text
        FROM (
            SELECT enumlabel::text as artifact
            FROM pg_enum 
            WHERE enumtypid = (SELECT oid FROM pg_type WHERE typname = 'artifacts')
        ) a
        WHERE NOT EXISTS (
            SELECT 1
            FROM artifact_resources_relation ar
            JOIN resource_tools_relation rt ON rt.resource = ar.resource AND rt.active = true
            JOIN agent_tools at ON at.tool_id = rt.tool_id AND at.active = true
            JOIN agent_artifact ag ON ag.id = at.agent_id
            WHERE ar.artifact::text = a.artifact
        )
        ORDER BY a.artifact
    """)
    results["artifacts_missing_agents"] = [
        r["artifact"] for r in artifacts_missing_agents
    ]

    # Query 13: Agents missing tools
    agents_missing_tools = await conn.fetch("""
        SELECT 
            ag.id as agent_id,
            (SELECT n.name FROM agent_names an JOIN names_resource n ON an.name_id = n.id WHERE an.agent_id = ag.id LIMIT 1) as agent_name
        FROM agent_artifact ag
        LEFT JOIN agent_tools at ON at.agent_id = ag.id AND at.active = true
        GROUP BY ag.id
        HAVING COUNT(DISTINCT at.tool_id) = 0
        ORDER BY ag.id
    """)
    results["agents_missing_tools"] = [dict(r) for r in agents_missing_tools]

    # Query 14: Agents missing prompts
    agents_missing_prompts = await conn.fetch("""
        SELECT 
            ag.id as agent_id,
            (SELECT n.name FROM agent_names an JOIN names_resource n ON an.name_id = n.id WHERE an.agent_id = ag.id LIMIT 1) as agent_name
        FROM agent_artifact ag
        LEFT JOIN agent_prompts ap ON ap.agent_id = ag.id AND ap.active = true
        WHERE ap.prompt_id IS NULL
        ORDER BY ag.id
    """)
    results["agents_missing_prompts"] = [dict(r) for r in agents_missing_prompts]

    # Query 15: Agents missing instructions
    agents_missing_instructions = await conn.fetch("""
        SELECT 
            ag.id as agent_id,
            (SELECT n.name FROM agent_names an JOIN names_resource n ON an.name_id = n.id WHERE an.agent_id = ag.id LIMIT 1) as agent_name
        FROM agent_artifact ag
        LEFT JOIN agent_instructions ai ON ai.agent_id = ag.id AND ai.active = true
        WHERE ai.instruction_id IS NULL
        ORDER BY ag.id
    """)
    results["agents_missing_instructions"] = [
        dict(r) for r in agents_missing_instructions
    ]

    # Query 16: Summary statistics
    stats = await conn.fetchrow("""
        SELECT 
            (SELECT COUNT(*) FROM pg_enum WHERE enumtypid = (SELECT oid FROM pg_type WHERE typname = 'resources')) as total_resources,
            (SELECT COUNT(DISTINCT resource) FROM resource_tools_relation rt 
             JOIN tool_artifact t ON t.id = rt.tool_id
             JOIN tool_flags tf ON tf.tool_id = t.id
             JOIN flags_resource f ON tf.flag_id = f.id
             WHERE f.name = 'active' AND tf.type = 'active'::type_tool_flags AND tf.value = true AND rt.active = true) as resources_with_tools,
            (SELECT COUNT(*) FROM tool_artifact t
             JOIN tool_flags tf ON tf.tool_id = t.id
             JOIN flags_resource f ON tf.flag_id = f.id
             WHERE f.name = 'active' AND tf.type = 'active'::type_tool_flags AND tf.value = true) as total_active_tools,
            (SELECT COUNT(*) FROM tool_artifact t 
             JOIN resource_tools_relation rt ON rt.tool_id = t.id
             JOIN tool_flags tf ON tf.tool_id = t.id
             JOIN flags_resource f ON tf.flag_id = f.id
             LEFT JOIN tool_templates tt ON tt.tool_id = t.id AND tt.type = 'output'::type_tool_templates
             LEFT JOIN schema_templates st ON st.template_id = tt.template_id
             WHERE f.name = 'active' AND tf.type = 'active'::type_tool_flags AND tf.value = true
             AND rt.active = true AND st.schema_id IS NULL) as tools_missing_output_schema,
            (SELECT COUNT(*) FROM tool_artifact t
             JOIN resource_tools_relation rt ON rt.tool_id = t.id
             JOIN tool_flags tf ON tf.tool_id = t.id
             JOIN flags_resource f ON tf.flag_id = f.id
             LEFT JOIN tool_schemas ts ON ts.tool_id = t.id
             WHERE f.name = 'active' AND tf.type = 'active'::type_tool_flags AND tf.value = true
             AND rt.active = true AND ts.schema_id IS NULL) as tools_missing_input_schema,
            (SELECT COUNT(*) FROM pg_enum WHERE enumtypid = (SELECT oid FROM pg_type WHERE typname = 'artifacts')) as total_artifacts,
            (SELECT COUNT(DISTINCT ag.id) FROM agent_artifact ag) as total_agents,
            (SELECT COUNT(DISTINCT ag.id) 
             FROM agent_artifact ag
             WHERE EXISTS (
                 SELECT 1 FROM agent_tools at WHERE at.agent_id = ag.id AND at.active = true
             )) as agents_with_tools,
            (SELECT COUNT(DISTINCT ag.id) 
             FROM agent_artifact ag
             WHERE EXISTS (
                 SELECT 1 FROM agent_prompts ap WHERE ap.agent_id = ag.id AND ap.active = true
             )) as agents_with_prompts,
            (SELECT COUNT(DISTINCT ag.id) 
             FROM agent_artifact ag
             WHERE EXISTS (
                 SELECT 1 FROM agent_instructions ai WHERE ai.agent_id = ag.id AND ai.active = true
             )) as agents_with_instructions
    """)
    results["statistics"] = dict(stats) if stats else {}

    return results


def print_report(results: dict[str, Any]) -> None:
    """Print comprehensive audit report.

    Args:
        results: Audit results dictionary
    """
    print("=" * 80)
    print("RESOURCE TOOLS TEMPLATE AUDIT REPORT")
    print("=" * 80)
    print()

    # Statistics
    stats = results["statistics"]
    print("📊 STATISTICS")
    print("-" * 80)
    print(f"Total resources in enum: {stats.get('total_resources', 0)}")
    print(f"Resources with tools: {stats.get('resources_with_tools', 0)}")
    print(f"Total active tools: {stats.get('total_active_tools', 0)}")
    print(f"Tools missing output schema: {stats.get('tools_missing_output_schema', 0)}")
    print(f"Tools missing input schema: {stats.get('tools_missing_input_schema', 0)}")
    print(f"Total artifacts: {stats.get('total_artifacts', 0)}")
    print(f"Total agents: {stats.get('total_agents', 0)}")
    print(f"Agents with tools: {stats.get('agents_with_tools', 0)}")
    print(f"Agents with prompts: {stats.get('agents_with_prompts', 0)}")
    print(f"Agents with instructions: {stats.get('agents_with_instructions', 0)}")
    print()

    # Resources missing tools
    missing_tools = results["resources_missing_tools"]
    if missing_tools:
        print("❌ RESOURCES MISSING TOOLS")
        print("-" * 80)
        for resource in missing_tools:
            print(f"  - {resource}")
        print()
    else:
        print("✅ All resources have tools")
        print()

    # Tools missing output schemas
    missing_output = results["tools_missing_output_schema"]
    if missing_output:
        print("⚠️  TOOLS MISSING OUTPUT SCHEMAS")
        print("-" * 80)
        for tool in missing_output:
            print(f"  - {tool['tool_name']} (resource: {tool['resource']})")
        print()
    else:
        print("✅ All tools have output schemas")
        print()

    # Tools missing input schemas (warning only)
    missing_input = results["tools_missing_input_schema"]
    if missing_input:
        print("ℹ️  TOOLS MISSING INPUT SCHEMAS (optional)")
        print("-" * 80)
        for tool in missing_input:
            print(f"  - {tool['tool_name']} (resource: {tool['resource']})")
        print()

    # Jinja validation errors
    jinja_errors = results["jinja_validation_errors"]
    if jinja_errors:
        print("❌ JINJA TEMPLATE VALIDATION ERRORS")
        print("-" * 80)
        for error in jinja_errors:
            print(f"  Tool: {error['tool_name']}")
            print(f"  Field: {error['output_field']}")
            print(f"  Error: {error['error']}")
            if "available_arguments" in error:
                print(
                    f"  Available arguments: {', '.join(error['available_arguments'])}"
                )
            print(f"  Template: {error['template']}")
            print()
    else:
        print("✅ All Jinja templates are valid")
        print()

    # Schema-table mismatches
    schema_mismatches = results["schema_table_mismatches"]
    if schema_mismatches:
        print("❌ SCHEMA-TABLE MISMATCHES")
        print("-" * 80)
        for mismatch in schema_mismatches:
            print(f"  Tool: {mismatch['tool_name']}")
            print(f"  Resource: {mismatch['resource']}")
            print(f"  Field: {mismatch['schema_field']}")
            print(f"  Error: {mismatch['error']}")
            print()
    else:
        print("✅ All schema fields exist in database tables")
        print()

    # Resources missing tables
    missing_tables = results["resources_missing_tables"]
    if missing_tables:
        print("⚠️  RESOURCES WITHOUT CORRESPONDING TABLES")
        print("-" * 80)
        for resource in missing_tables:
            print(f"  - {resource}")
        print()

    # Output mapping gaps
    output_gaps = results["output_mapping_gaps"]
    if output_gaps:
        print("❌ OUTPUT MAPPING GAPS (Required columns not covered)")
        print("-" * 80)
        for gap in output_gaps:
            print(f"  Table: {gap['table_name']}")
            print(f"  Column: {gap['column_name']} ({gap['data_type']})")
            print(
                f"  Nullable: {gap['is_nullable']}, Default: {gap['column_default'] or 'None'}"
            )
            print()
    else:
        print("✅ All required columns are covered by output schemas")
        print()

    # Granular schema validation
    granular = results["granular_schema_validation"]
    type_mismatches = [
        g for g in granular if g["type_compatibility"] == "TYPE_MISMATCH"
    ]
    missing_columns = [
        g for g in granular if g["type_compatibility"] == "MISSING_COLUMN"
    ]
    nullable_warnings = [
        g for g in granular if "WARNING" in g.get("nullable_compatibility", "")
    ]

    if type_mismatches or missing_columns or nullable_warnings:
        print("🔍 GRANULAR SCHEMA-TABLE VALIDATION")
        print("-" * 80)
        if missing_columns:
            print(f"❌ {len(missing_columns)} schema fields missing from tables")
            for item in missing_columns[:10]:
                print(
                    f"  - {item['resource']}.{item['schema_field_name']} (tool: {item['tool_name']})"
                )
            if len(missing_columns) > 10:
                print(f"  ... and {len(missing_columns) - 10} more")
            print()
        if type_mismatches:
            print(f"⚠️  {len(type_mismatches)} data type mismatches")
            for item in type_mismatches[:10]:
                print(
                    f"  - {item['resource']}.{item['schema_field_name']}: schema={item['schema_field_type']}, table={item['table_data_type']}"
                )
            if len(type_mismatches) > 10:
                print(f"  ... and {len(type_mismatches) - 10} more")
            print()
        if nullable_warnings:
            print(f"⚠️  {len(nullable_warnings)} required/nullable mismatches")
            for item in nullable_warnings[:10]:
                print(
                    f"  - {item['resource']}.{item['schema_field_name']}: {item['nullable_compatibility']}"
                )
            if len(nullable_warnings) > 10:
                print(f"  ... and {len(nullable_warnings) - 10} more")
            print()
    else:
        print("✅ All schema fields match table structure (data types, nullable)")
        print()

    # INSERT column coverage
    insert_coverage = results["insert_column_coverage"]
    missing_from_schema = [
        i for i in insert_coverage if i["coverage_status"] == "MISSING_FROM_SCHEMA"
    ]
    if missing_from_schema:
        print("⚠️  INSERT COLUMNS MISSING FROM OUTPUT SCHEMAS")
        print("-" * 80)
        print(
            f"Found {len(missing_from_schema)} INSERT columns not covered by output schemas"
        )
        print("(Excluding system-managed columns)")
        print()
        for item in missing_from_schema[:20]:
            print(f"  - {item['proname']}: {item['insert_column']}")
        if len(missing_from_schema) > 20:
            print(f"  ... and {len(missing_from_schema) - 20} more")
        print()
    else:
        print("✅ All INSERT columns are covered by output schemas")
        print()

    # Artifacts missing agents
    artifacts_missing = results["artifacts_missing_agents"]
    if artifacts_missing:
        print("❌ ARTIFACTS MISSING AGENTS")
        print("-" * 80)
        for artifact in artifacts_missing:
            print(f"  - {artifact}")
        print()
    else:
        print("✅ All artifacts have agents")
        print()

    # Agents missing tools
    agents_no_tools = results["agents_missing_tools"]
    if agents_no_tools:
        print("❌ AGENTS MISSING TOOLS")
        print("-" * 80)
        for agent in agents_no_tools:
            print(f"  - {agent['agent_name'] or 'Unknown'} (ID: {agent['agent_id']})")
        print()
    else:
        print("✅ All agents have tools")
        print()

    # Agents missing prompts
    agents_no_prompts = results["agents_missing_prompts"]
    if agents_no_prompts:
        print("⚠️  AGENTS MISSING PROMPTS")
        print("-" * 80)
        for agent in agents_no_prompts:
            print(f"  - {agent['agent_name'] or 'Unknown'} (ID: {agent['agent_id']})")
        print()
    else:
        print("✅ All agents have prompts")
        print()

    # Agents missing instructions
    agents_no_instructions = results["agents_missing_instructions"]
    if agents_no_instructions:
        print("⚠️  AGENTS MISSING INSTRUCTIONS")
        print("-" * 80)
        for agent in agents_no_instructions:
            print(f"  - {agent['agent_name'] or 'Unknown'} (ID: {agent['agent_id']})")
        print()
    else:
        print("✅ All agents have instructions")
        print()

    # Summary
    print("=" * 80)
    total_issues = (
        len(missing_tools)
        + len(missing_output)
        + len(jinja_errors)
        + len(schema_mismatches)
        + len(output_gaps)
        + len(artifacts_missing)
        + len(agents_no_tools)
    )

    if total_issues == 0:
        print("✅ AUDIT PASSED: No issues found!")
    else:
        print(f"⚠️  AUDIT FOUND {total_issues} ISSUE(S)")
        print(f"   - {len(missing_tools)} resources missing tools")
        print(f"   - {len(missing_output)} tools missing output schemas")
        print(f"   - {len(jinja_errors)} Jinja template errors")
        print(f"   - {len(schema_mismatches)} schema-table mismatches")
        print(f"   - {len(output_gaps)} output mapping gaps")
        print(f"   - {len(artifacts_missing)} artifacts missing agents")
        print(f"   - {len(agents_no_tools)} agents missing tools")
        print(f"   - {len(agents_no_prompts)} agents missing prompts (warnings)")
        print(
            f"   - {len(agents_no_instructions)} agents missing instructions (warnings)"
        )
    print("=" * 80)


async def main() -> int:
    """Main entry point."""
    # Get database connection info from environment
    db_user = os.getenv("DB_USER", "myuser")
    db_password = os.getenv("DB_PASSWORD", "mypassword")
    db_name = os.getenv("DB_NAME", "mydb")
    db_host = os.getenv("DB_HOST", "localhost")
    db_port = int(os.getenv("DB_PORT", "5432"))

    db_url = f"postgresql://{db_user}:{db_password}@{db_host}:{db_port}/{db_name}"

    # Connect to database
    try:
        conn = await asyncpg.connect(db_url)
    except Exception as e:
        print(f"❌ Failed to connect to database: {e}")
        print(f"   URL: postgresql://{db_user}:***@{db_host}:{db_port}/{db_name}")
        return 1

    try:
        # Run audit
        results = await run_audit(conn)

        # Print report
        print_report(results)

        # Return exit code based on issues found
        total_issues = (
            len(results["resources_missing_tools"])
            + len(results["tools_missing_output_schema"])
            + len(results["jinja_validation_errors"])
            + len(results["schema_table_mismatches"])
            + len(results["output_mapping_gaps"])
            + len(results["artifacts_missing_agents"])
            + len(results["agents_missing_tools"])
        )

        return 1 if total_issues > 0 else 0

    except Exception as e:
        print(f"❌ Error running audit: {e}")
        import traceback

        traceback.print_exc()
        return 1
    finally:
        await conn.close()


if __name__ == "__main__":
    import asyncio

    exit_code = asyncio.run(main())
    sys.exit(exit_code)
