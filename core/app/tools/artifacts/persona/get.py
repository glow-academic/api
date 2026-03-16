"""Persona artifact GET — reusable data-access layer."""

from uuid import UUID

import asyncpg

from app.tools.artifacts.persona.types import GetPersonasResponse

TABLE = "persona_artifact"

# (flag_name, junction_table, junction_column, response_field)
JUNCTIONS: list[tuple[str, str, str, str]] = [
    ("names", "persona_names_junction", "names_id", "name_ids"),
    (
        "descriptions",
        "persona_descriptions_junction",
        "descriptions_id",
        "description_ids",
    ),
    ("colors", "persona_colors_junction", "colors_id", "color_ids"),
    ("departments", "persona_departments_junction", "departments_id", "department_ids"),
    ("examples", "persona_examples_junction", "examples_id", "example_ids"),
    ("flags", "persona_flags_junction", "flags_id", "flag_ids"),
    ("icons", "persona_icons_junction", "icons_id", "icon_ids"),
    (
        "instructions",
        "persona_instructions_junction",
        "instructions_id",
        "instruction_ids",
    ),
    (
        "parameter_fields",
        "persona_parameter_fields_junction",
        "parameter_fields_id",
        "parameter_field_ids",
    ),
    ("personas", "persona_personas_junction", "personas_id", "persona_ids"),
    ("voices", "persona_voices_junction", "voices_id", "voice_ids"),
]


async def get_personas(
    conn: asyncpg.Connection,
    ids: list[UUID],
    *,
    active: bool | None = True,
    names: bool = False,
    descriptions: bool = False,
    colors: bool = False,
    departments: bool = False,
    examples: bool = False,
    flags: bool = False,
    icons: bool = False,
    instructions: bool = False,
    parameter_fields: bool = False,
    personas: bool = False,
    voices: bool = False,
) -> list[GetPersonasResponse]:
    """Get persona artifacts by IDs with optional junction ID fetching."""
    if not ids:
        return []

    flags_map = {
        "names": names,
        "descriptions": descriptions,
        "colors": colors,
        "departments": departments,
        "examples": examples,
        "flags": flags,
        "icons": icons,
        "instructions": instructions,
        "parameter_fields": parameter_fields,
        "personas": personas,
        "voices": voices,
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
    joins: list[str] = []

    for i, (table, col, field) in enumerate(active_junctions):
        alias = f"j{i}"
        joins.append(
            f"LEFT JOIN {table} {alias} ON {alias}.persona_id = p.id AND {alias}.active = true"
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
            # else stays None (default)
        results.append(GetPersonasResponse(**data))

    return results
