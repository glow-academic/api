"""Rubric artifact GET — reusable data-access layer."""

from uuid import UUID

import asyncpg

from app.tools.artifacts.rubric.types import GetRubricsResponse

TABLE = "rubric_artifact"

# (flag_name, junction_table, junction_column, response_field)
JUNCTIONS: list[tuple[str, str, str, str]] = [
    ("names", "rubric_names_junction", "names_id", "name_ids"),
    (
        "descriptions",
        "rubric_descriptions_junction",
        "descriptions_id",
        "description_ids",
    ),
    ("departments", "rubric_departments_junction", "departments_id", "department_ids"),
    ("flags", "rubric_flags_junction", "flags_id", "flag_ids"),
    ("points", "rubric_points_junction", "points_id", "point_ids"),
    (
        "standard_groups",
        "rubric_standard_groups_junction",
        "standard_groups_id",
        "standard_group_ids",
    ),
    ("standards", "rubric_standards_junction", "standards_id", "standard_ids"),
    ("rubrics", "rubric_rubrics_junction", "rubrics_id", "rubric_ids"),
]


async def get_rubrics(
    conn: asyncpg.Connection,
    ids: list[UUID],
    *,
    active: bool | None = True,
    names: bool = False,
    descriptions: bool = False,
    departments: bool = False,
    flags: bool = False,
    points: bool = False,
    standard_groups: bool = False,
    standards: bool = False,
    rubrics: bool = False,
) -> list[GetRubricsResponse]:
    """Get rubric artifacts by IDs with optional junction ID fetching."""
    if not ids:
        return []

    flags_map = {
        "names": names,
        "descriptions": descriptions,
        "departments": departments,
        "flags": flags,
        "points": points,
        "standard_groups": standard_groups,
        "standards": standards,
        "rubrics": rubrics,
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
            f"LEFT JOIN {table} {alias} ON {alias}.rubric_id = p.id AND {alias}.active = true"
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
        results.append(GetRubricsResponse(**data))

    return results
