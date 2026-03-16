"""Simulation artifact GET — reusable data-access layer."""

from uuid import UUID

import asyncpg

from app.tools.artifacts.simulation.types import GetSimulationsResponse

TABLE = "simulation_artifact"
ARTIFACT_FK = "simulation_id"

# (flag_name, junction_table, junction_column, response_field)
JUNCTIONS: list[tuple[str, str, str, str]] = [
    ("names", "simulation_names_junction", "names_id", "name_ids"),
    (
        "descriptions",
        "simulation_descriptions_junction",
        "descriptions_id",
        "description_ids",
    ),
    (
        "departments",
        "simulation_departments_junction",
        "departments_id",
        "department_ids",
    ),
    ("flags", "simulation_flags_junction", "flags_id", "flag_ids"),
    ("scenarios", "simulation_scenarios_junction", "scenarios_id", "scenario_ids"),
    (
        "scenario_flags",
        "simulation_scenario_flags_junction",
        "scenario_flags_id",
        "scenario_flag_ids",
    ),
    (
        "scenario_positions",
        "simulation_scenario_positions_junction",
        "scenario_positions_id",
        "scenario_position_ids",
    ),
    (
        "scenario_rubrics",
        "simulation_scenario_rubrics_junction",
        "scenario_rubrics_id",
        "scenario_rubric_ids",
    ),
    (
        "scenario_time_limits",
        "simulation_scenario_time_limits_junction",
        "scenario_time_limits_id",
        "scenario_time_limit_ids",
    ),
    (
        "simulations",
        "simulation_simulations_junction",
        "simulations_id",
        "simulation_ids",
    ),
]


async def get_simulations(
    conn: asyncpg.Connection,
    ids: list[UUID],
    *,
    active: bool | None = True,
    names: bool = False,
    descriptions: bool = False,
    departments: bool = False,
    flags: bool = False,
    scenarios: bool = False,
    scenario_flags: bool = False,
    scenario_positions: bool = False,
    scenario_rubrics: bool = False,
    scenario_time_limits: bool = False,
    simulations: bool = False,
) -> list[GetSimulationsResponse]:
    """Get simulation artifacts by IDs with optional junction ID fetching."""
    if not ids:
        return []

    flags_map = {
        "names": names,
        "descriptions": descriptions,
        "departments": departments,
        "flags": flags,
        "scenarios": scenarios,
        "scenario_flags": scenario_flags,
        "scenario_positions": scenario_positions,
        "scenario_rubrics": scenario_rubrics,
        "scenario_time_limits": scenario_time_limits,
        "simulations": simulations,
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
        results.append(GetSimulationsResponse(**data))

    return results
