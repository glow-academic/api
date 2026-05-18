"""Simulation artifact documentation."""

import asyncpg

from app.infra.docs.get_operation_info import get_operation_info
from app.infra.docs.get_table_info import get_table_info
from app.infra.docs.types import DocsResponse
from app.tools.artifacts.simulation.create import create_simulation
from app.tools.artifacts.simulation.delete import delete_simulations
from app.tools.artifacts.simulation.get import get_simulations
from app.tools.artifacts.simulation.search import search_simulations
from app.tools.artifacts.simulation.update import update_simulation


async def get_simulation_docs(conn: asyncpg.Connection) -> DocsResponse:
    """Get full documentation for the simulation artifact."""
    artifact_table = await get_table_info(conn, "simulation_artifact")
    tables = [t for t in [artifact_table] if t is not None]

    return DocsResponse(
        name="simulation",
        type="artifact",
        description=(
            "Simulations define ordered collections of scenarios for learner practice sessions. "
            "Each simulation links to resources (names, descriptions, departments, scenarios, "
            "scenario_flags, scenario_positions, scenario_rubrics, scenario_time_limits) via "
            "junction tables."
        ),
        tables=tables,
        operations=[
            get_operation_info(
                create_simulation,
                description="Creates a new simulation artifact with optional resource links.",
            ),
            get_operation_info(
                update_simulation,
                description="Updates an existing simulation's resource links.",
            ),
            get_operation_info(
                get_simulations,
                description="Batch retrieves simulations by IDs with optional junction data.",
            ),
            get_operation_info(
                search_simulations,
                description="Filtered paginated search returning matching simulation IDs.",
            ),
            get_operation_info(
                delete_simulations,
                description="Deletes simulations by IDs. Supports soft delete (active=false) or hard delete (cascade).",
            ),
        ],
    )
