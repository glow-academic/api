"""Simulation Positions resource documentation."""

import asyncpg

from app.infra.docs.get_operation_info import get_operation_info
from app.infra.docs.get_table_info import get_table_info
from app.infra.docs.types import DocsResponse
from app.tools.resources.simulation_positions.create import (
    create_simulation_position,
)
from app.tools.resources.simulation_positions.get import (
    get_simulation_positions,
)
from app.tools.resources.simulation_positions.search import (
    search_simulation_positions,
)


async def get_simulation_positions_docs(conn: asyncpg.Connection) -> DocsResponse:
    """Get full documentation for the simulation positions resource."""
    resource_table = await get_table_info(conn, "simulation_positions_resource")
    tables = [t for t in [resource_table] if t is not None]

    return DocsResponse(
        name="simulation_positions",
        type="resource",
        description="Simulation position orderings within cohorts.",
        tables=tables,
        operations=[
            get_operation_info(
                create_simulation_position,
                description="Creates a new simulation positions resource.",
            ),
            get_operation_info(
                get_simulation_positions,
                description="Batch retrieves simulation positions by IDs.",
            ),
            get_operation_info(
                search_simulation_positions,
                description="Filtered paginated search returning matching simulation positions.",
            ),
        ],
    )
