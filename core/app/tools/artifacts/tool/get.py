"""Tool artifact GET — reusable data-access layer."""

from uuid import UUID

import asyncpg

from app.tools.artifacts.tool.types import GetToolsResponse

TABLE = "tool_artifact"
ARTIFACT_FK = "tool_id"

# (flag_name, junction_table, junction_column, response_field)
JUNCTIONS: list[tuple[str, str, str, str]] = [
    ("names", "tool_names_junction", "names_id", "name_ids"),
    (
        "descriptions",
        "tool_descriptions_junction",
        "descriptions_id",
        "description_ids",
    ),
    ("departments", "tool_departments_junction", "departments_id", "department_ids"),
    ("flags", "tool_flags_junction", "flags_id", "flag_ids"),
    ("args", "tool_args_junction", "args_id", "args_ids"),
    (
        "args_outputs",
        "tool_args_outputs_junction",
        "args_outputs_id",
        "args_outputs_ids",
    ),
    (
        "arg_positions",
        "tool_arg_positions_junction",
        "arg_positions_id",
        "arg_positions_ids",
    ),
    ("permissions", "tool_permissions_junction", "permissions_id", "permission_ids"),
    (
        "instructions",
        "tool_instructions_junction",
        "instructions_id",
        "instruction_ids",
    ),
    ("tools", "tool_tools_junction", "tools_id", "tool_ids"),
]


async def get_tools(
    conn: asyncpg.Connection,
    ids: list[UUID],
    *,
    active: bool | None = True,
    names: bool = False,
    descriptions: bool = False,
    departments: bool = False,
    flags: bool = False,
    args: bool = False,
    args_outputs: bool = False,
    arg_positions: bool = False,
    permissions: bool = False,
    instructions: bool = False,
    tools: bool = False,
) -> list[GetToolsResponse]:
    """Get tool artifacts by IDs with optional junction ID fetching."""
    if not ids:
        return []

    flags_map = {
        "names": names,
        "descriptions": descriptions,
        "departments": departments,
        "flags": flags,
        "args": args,
        "args_outputs": args_outputs,
        "arg_positions": arg_positions,
        "permissions": permissions,
        "instructions": instructions,
        "tools": tools,
    }

    active_junctions = [
        (table, col, field) for flag, table, col, field in JUNCTIONS if flags_map[flag]
    ]

    # Build dynamic query
    columns = [
        "p.id",
        "p.created_at",
        "p.updated_at",
        "p.generated",
        "p.mcp",
        "p.active",
    ]
    for table, col, field in active_junctions:
        columns.append(
            f"(SELECT array_agg(DISTINCT {col}) "
            f"FROM {table} "
            f"WHERE {ARTIFACT_FK} = p.id AND active) AS {field}"
        )

    where_clauses = ["p.id = ANY($1)"]
    params: list[object] = [ids]
    if active is not None:
        where_clauses.append(f"p.active = ${len(params) + 1}")
        params.append(active)

    query = f"""
        SELECT {", ".join(columns)}
        FROM {TABLE} p
        WHERE {" AND ".join(where_clauses)}
    """

    rows = await conn.fetch(query, *params)

    results = []
    for r in rows:
        data: dict = {
            "id": r["id"],
            "created_at": r["created_at"],
            "updated_at": r["updated_at"],
            "generated": r["generated"],
            "mcp": r["mcp"],
            "active": r["active"],
        }
        for _, _, _, field in JUNCTIONS:
            if field in dict(r):
                data[field] = r[field] or []
        results.append(GetToolsResponse(**data))

    return results
