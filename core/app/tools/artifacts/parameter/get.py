"""Parameter artifact GET — reusable data-access layer."""

from uuid import UUID

import asyncpg

from app.tools.artifacts.parameter.types import GetParametersResponse

TABLE = "parameter_artifact"

# (flag_name, junction_table, junction_column, response_field)
JUNCTIONS: list[tuple[str, str, str, str]] = [
    ("names", "parameter_names_junction", "names_id", "name_ids"),
    (
        "descriptions",
        "parameter_descriptions_junction",
        "descriptions_id",
        "description_ids",
    ),
    (
        "departments",
        "parameter_departments_junction",
        "departments_id",
        "department_ids",
    ),
    ("flags", "parameter_flags_junction", "flags_id", "flag_ids"),
    ("fields", "parameter_fields_junction", "fields_id", "field_ids"),
    ("parameters", "parameter_parameters_junction", "parameters_id", "parameter_ids"),
]


async def get_parameters(
    conn: asyncpg.Connection,
    ids: list[UUID],
    *,
    active: bool | None = True,
    names: bool = False,
    descriptions: bool = False,
    departments: bool = False,
    flags: bool = False,
    fields: bool = False,
    parameters: bool = False,
) -> list[GetParametersResponse]:
    """Get parameter artifacts by IDs with optional junction ID fetching."""
    if not ids:
        return []

    flags_map = {
        "names": names,
        "descriptions": descriptions,
        "departments": departments,
        "flags": flags,
        "fields": fields,
        "parameters": parameters,
    }

    active_junctions = [
        (table, col, field) for flag, table, col, field in JUNCTIONS if flags_map[flag]
    ]

    columns = [
        "p.id",
        "p.created_at",
        "p.updated_at",
        "p.generated",
        "p.mcp",
        "p.active",
    ]
    joins: list[str] = []

    for i, (table, col, field) in enumerate(active_junctions):
        alias = f"j{i}"
        joins.append(
            f"LEFT JOIN {table} {alias} ON {alias}.parameter_id = p.id AND {alias}.active = true"
        )
        columns.append(
            f"ARRAY_AGG(DISTINCT {alias}.{col}) FILTER (WHERE {alias}.{col} IS NOT NULL) AS {field}"
        )

    where_clauses = ["p.id = ANY($1)"]
    params: list[object] = [ids]
    if active is not None:
        where_clauses.append(f"p.active = ${len(params) + 1}")
        params.append(active)

    query = f"""
        SELECT {", ".join(columns)}
        FROM {TABLE} p
        {" ".join(joins)}
        WHERE {" AND ".join(where_clauses)}
        GROUP BY p.id, p.created_at, p.updated_at, p.generated, p.mcp, p.active
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
        results.append(GetParametersResponse(**data))

    return results
