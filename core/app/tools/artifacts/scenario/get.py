"""Scenario artifact GET — reusable data-access layer."""

from uuid import UUID

import asyncpg

from app.tools.artifacts.scenario.types import GetScenariosResponse

TABLE = "scenario_artifact"
ARTIFACT_FK = "scenario_id"

# (flag_name, junction_table, junction_column, response_field)
JUNCTIONS: list[tuple[str, str, str, str]] = [
    ("names", "scenario_names_junction", "names_id", "name_ids"),
    (
        "descriptions",
        "scenario_descriptions_junction",
        "descriptions_id",
        "description_ids",
    ),
    (
        "departments",
        "scenario_departments_junction",
        "departments_id",
        "department_ids",
    ),
    ("flags", "scenario_flags_junction", "flags_id", "flag_ids"),
    ("documents", "scenario_documents_junction", "documents_id", "document_ids"),
    ("images", "scenario_images_junction", "images_id", "image_ids"),
    ("objectives", "scenario_objectives_junction", "objectives_id", "objective_ids"),
    ("options", "scenario_options_junction", "options_id", "option_ids"),
    (
        "parameter_fields",
        "scenario_parameter_fields_junction",
        "parameter_fields_id",
        "parameter_field_ids",
    ),
    ("personas", "scenario_personas_junction", "personas_id", "persona_ids"),
    (
        "problem_statements",
        "scenario_problem_statements_junction",
        "problem_statements_id",
        "problem_statement_ids",
    ),
    ("questions", "scenario_questions_junction", "questions_id", "question_ids"),
    ("videos", "scenario_videos_junction", "videos_id", "video_ids"),
    ("scenarios", "scenario_scenarios_junction", "scenarios_id", "scenario_ids"),
]


async def get_scenarios(
    conn: asyncpg.Connection,
    ids: list[UUID],
    *,
    active: bool | None = True,
    names: bool = False,
    descriptions: bool = False,
    departments: bool = False,
    flags: bool = False,
    documents: bool = False,
    images: bool = False,
    objectives: bool = False,
    options: bool = False,
    parameter_fields: bool = False,
    personas: bool = False,
    problem_statements: bool = False,
    questions: bool = False,
    videos: bool = False,
    scenarios: bool = False,
) -> list[GetScenariosResponse]:
    """Get scenario artifacts by IDs with optional junction ID fetching."""
    if not ids:
        return []

    flags_map = {
        "names": names,
        "descriptions": descriptions,
        "departments": departments,
        "flags": flags,
        "documents": documents,
        "images": images,
        "objectives": objectives,
        "options": options,
        "parameter_fields": parameter_fields,
        "personas": personas,
        "problem_statements": problem_statements,
        "questions": questions,
        "videos": videos,
        "scenarios": scenarios,
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
            f"LEFT JOIN {table} {alias} ON {alias}.{ARTIFACT_FK} = p.id AND {alias}.active = true"
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
        results.append(GetScenariosResponse(**data))

    return results
