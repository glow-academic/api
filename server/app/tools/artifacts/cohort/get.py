"""Cohort artifact GET — reusable data-access layer."""

from uuid import UUID

import asyncpg

from app.tools.artifacts.cohort.types import GetCohortsResponse

TABLE = "cohort_artifact"
ARTIFACT_FK = "cohort_id"

# (flag_name, junction_table, junction_column, response_field)
JUNCTIONS: list[tuple[str, str, str, str]] = [
    ("names", "cohort_names_junction", "names_id", "name_ids"),
    (
        "descriptions",
        "cohort_descriptions_junction",
        "descriptions_id",
        "description_ids",
    ),
    ("departments", "cohort_departments_junction", "departments_id", "department_ids"),
    ("flags", "cohort_flags_junction", "flags_id", "flag_ids"),
    ("profiles", "cohort_profiles_junction", "profiles_id", "profiles_ids"),
    (
        "profile_personas",
        "cohort_profile_personas_junction",
        "profile_personas_id",
        "profile_persona_ids",
    ),
    ("simulations", "cohort_simulations_junction", "simulations_id", "simulation_ids"),
    (
        "simulation_availability",
        "cohort_simulation_availability_junction",
        "simulation_availability_id",
        "simulation_availability_ids",
    ),
    (
        "simulation_positions",
        "cohort_simulation_positions_junction",
        "simulation_positions_id",
        "simulation_position_ids",
    ),
    ("cohorts", "cohort_cohorts_junction", "cohorts_id", "cohort_ids"),
]


async def get_cohorts(
    conn: asyncpg.Connection,
    ids: list[UUID],
    *,
    active: bool | None = True,
    names: bool = False,
    descriptions: bool = False,
    departments: bool = False,
    flags: bool = False,
    profiles: bool = False,
    profile_personas: bool = False,
    simulations: bool = False,
    simulation_availability: bool = False,
    simulation_positions: bool = False,
    cohorts: bool = False,
) -> list[GetCohortsResponse]:
    """Get cohort artifacts by IDs with optional junction ID fetching."""
    if not ids:
        return []

    flags_map = {
        "names": names,
        "descriptions": descriptions,
        "departments": departments,
        "flags": flags,
        "profiles": profiles,
        "profile_personas": profile_personas,
        "simulations": simulations,
        "simulation_availability": simulation_availability,
        "simulation_positions": simulation_positions,
        "cohorts": cohorts,
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
        results.append(GetCohortsResponse(**data))

    return results
