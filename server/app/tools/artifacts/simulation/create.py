"""Simulation artifact CREATE — tool layer."""

from uuid import UUID

import asyncpg

from app.infra.junctions import (
    insert_multi,
    insert_single,
)
from app.tools.artifacts.simulation.types import CreateSimulationResponse

OWNER_COL = "simulation_id"

# (junction_table, resource_column)
SINGLE_JUNCTIONS: list[tuple[str, str]] = [
    ("simulation_names_junction", "names_id"),
    ("simulation_descriptions_junction", "descriptions_id"),
]

MULTI_JUNCTIONS: list[tuple[str, str]] = [
    ("simulation_departments_junction", "departments_id"),
    ("simulation_scenarios_junction", "scenarios_id"),
    ("simulation_scenario_flags_junction", "scenario_flags_id"),
    ("simulation_scenario_positions_junction", "scenario_positions_id"),
    ("simulation_scenario_rubrics_junction", "scenario_rubrics_id"),
    ("simulation_scenario_time_limits_junction", "scenario_time_limits_id"),
    ("simulation_simulations_junction", "simulations_id"),
]


async def create_simulation(
    conn: asyncpg.Connection,
    *,
    id: UUID | None = None,
    name_id: UUID | None = None,
    description_id: UUID | None = None,
    department_ids: list[UUID] | None = None,
    flag_ids: list[UUID] | None = None,
    scenario_ids: list[UUID] | None = None,
    scenario_flag_ids: list[UUID] | None = None,
    scenario_position_ids: list[UUID] | None = None,
    scenario_rubric_ids: list[UUID] | None = None,
    scenario_time_limit_ids: list[UUID] | None = None,
    simulation_ids: list[UUID] | None = None,
    active: bool | None = None,
    soft: bool = False,
    generated: bool = False,
    mcp: bool = False,
) -> CreateSimulationResponse:
    """Create a simulation artifact with optional junction links."""
    is_active = not soft if active is None else active
    simulation_id: UUID = await conn.fetchval(
        """
        INSERT INTO simulation_artifact (id, active, generated, mcp)
        VALUES (COALESCE($4, uuidv7()), $1, $2, $3)
        RETURNING id
        """,
        is_active,
        generated,
        mcp,
        id,
    )

    # Single-select junctions
    single_vals = [name_id, description_id]
    for (table, col), val in zip(SINGLE_JUNCTIONS, single_vals):
        if val is not None:
            await insert_single(
                conn,
                table=table,
                owner_col=OWNER_COL,
                owner_id=simulation_id,
                resource_col=col,
                resource_id=val,
                generated=generated,
                mcp=mcp,
            )

    # Multi-select junctions (simple)
    multi_vals = [
        department_ids,
        scenario_ids,
        scenario_flag_ids,
        scenario_position_ids,
        scenario_rubric_ids,
        scenario_time_limit_ids,
        simulation_ids,
    ]
    for (table, col), vals in zip(MULTI_JUNCTIONS, multi_vals):
        if vals:
            await insert_multi(
                conn,
                table=table,
                owner_col=OWNER_COL,
                owner_id=simulation_id,
                resource_col=col,
                resource_ids=vals,
                generated=generated,
                mcp=mcp,
            )

    # Flags
    if flag_ids:
        await insert_multi(
            conn,
            table="simulation_flags_junction",
            owner_col=OWNER_COL,
            owner_id=simulation_id,
            resource_col="flags_id",
            resource_ids=flag_ids,
            generated=generated,
            mcp=mcp,
        )

    return CreateSimulationResponse(id=simulation_id)
