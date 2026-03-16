"""Simulation artifact UPDATE — tool layer.

Efficient junction updates: only deactivate removed IDs, upsert new ones,
and touch (updated_at) unchanged ones.
"""

from typing import Any
from uuid import UUID

import asyncpg

from app.infra.junctions import (
    upsert_multi,
    upsert_single,
)
from app.tools.artifacts.simulation.types import UpdateSimulationResponse

_UNSET: Any = object()

OWNER_COL = "simulation_id"

# (junction_table, resource_column, pk_constraint)
SINGLE_JUNCTIONS: list[tuple[str, str, str]] = [
    ("simulation_names_junction", "names_id", "simulation_names_pkey"),
    (
        "simulation_descriptions_junction",
        "descriptions_id",
        "simulation_descriptions_pkey",
    ),
]

MULTI_JUNCTIONS: list[tuple[str, str, str]] = [
    (
        "simulation_departments_junction",
        "departments_id",
        "simulation_departments_pkey",
    ),
    ("simulation_scenarios_junction", "scenarios_id", "simulation_scenarios_pkey"),
    (
        "simulation_scenario_flags_junction",
        "scenario_flags_id",
        "simulation_scenario_flags_new_pkey",
    ),
    (
        "simulation_scenario_positions_junction",
        "scenario_positions_id",
        "simulation_scenario_positions_pkey",
    ),
    (
        "simulation_scenario_rubrics_junction",
        "scenario_rubrics_id",
        "simulation_scenario_rubrics_pkey",
    ),
    (
        "simulation_scenario_time_limits_junction",
        "scenario_time_limits_id",
        "simulation_scenario_time_limits_pkey",
    ),
    (
        "simulation_simulations_junction",
        "simulations_id",
        "simulation_simulations_junction_pkey",
    ),
]


async def update_simulation(
    conn: asyncpg.Connection,
    simulation_id: UUID,
    *,
    # Single-select junctions (_UNSET = don't change)
    name_id: UUID | Any = _UNSET,
    description_id: UUID | Any = _UNSET,
    # Multi-select junctions (None = don't change, [] = remove all)
    department_ids: list[UUID] | None = None,
    flag_ids: list[UUID] | None = None,
    scenario_ids: list[UUID] | None = None,
    scenario_flag_ids: list[UUID] | None = None,
    scenario_position_ids: list[UUID] | None = None,
    scenario_rubric_ids: list[UUID] | None = None,
    scenario_time_limit_ids: list[UUID] | None = None,
    simulation_ids: list[UUID] | None = None,
    # Base columns
    active: bool | Any = _UNSET,
    soft: bool = False,
    mcp: bool = False,
) -> UpdateSimulationResponse:
    """Update a simulation artifact with efficient junction diffs."""
    # soft=True forces active=false regardless of the active parameter
    if soft:
        active = False

    # 1. Update artifact row
    if active is not _UNSET:
        await conn.execute(
            "UPDATE simulation_artifact SET updated_at = NOW(), active = $2, mcp = $3 "
            "WHERE id = $1",
            simulation_id,
            active,
            mcp,
        )
    else:
        await conn.execute(
            "UPDATE simulation_artifact SET updated_at = NOW(), mcp = $2 WHERE id = $1",
            simulation_id,
            mcp,
        )

    # 2. Single-select junctions
    single_vals = [name_id, description_id]
    for (table, col, constraint), val in zip(SINGLE_JUNCTIONS, single_vals):
        if val is not _UNSET:
            await upsert_single(
                conn,
                table=table,
                owner_col=OWNER_COL,
                owner_id=simulation_id,
                resource_col=col,
                resource_id=val,
                constraint=constraint,
                mcp=mcp,
            )

    # 3. Multi-select junctions (simple)
    multi_vals: list[list[UUID] | None] = [
        department_ids,
        scenario_ids,
        scenario_flag_ids,
        scenario_position_ids,
        scenario_rubric_ids,
        scenario_time_limit_ids,
        simulation_ids,
    ]
    for (table, col, constraint), vals in zip(MULTI_JUNCTIONS, multi_vals):
        if vals is not None:
            await upsert_multi(
                conn,
                table=table,
                owner_col=OWNER_COL,
                owner_id=simulation_id,
                resource_col=col,
                resource_ids=vals,
                constraint=constraint,
                mcp=mcp,
            )

    # 4. Flags
    if flag_ids is not None:
        await upsert_multi(
            conn,
            table="simulation_flags_junction",
            owner_col=OWNER_COL,
            owner_id=simulation_id,
            resource_col="flags_id",
            resource_ids=flag_ids,
            constraint="simulation_flags_pkey",
            mcp=mcp,
        )

    return UpdateSimulationResponse(id=simulation_id)
