"""Simulations resource documentation."""

import asyncpg

from app.infra.docs.get_operation_info import get_operation_info
from app.infra.docs.get_table_info import get_table_info
from app.infra.docs.types import DocsResponse
from app.tools.resources.simulations.create import create_simulation
from app.tools.resources.simulations.get import get_simulations
from app.tools.resources.simulations.search import search_simulations


async def get_simulations_docs(conn: asyncpg.Connection) -> DocsResponse:
    """Get full documentation for the simulations resource."""
    resource_table = await get_table_info(conn, "simulations_resource")
    tables = [t for t in [resource_table] if t is not None]

    return DocsResponse(
        name="simulations",
        type="resource",
        description="Simulation reference IDs linking to simulation artifacts.",
        tables=tables,
        operations=[
            get_operation_info(
                create_simulation,
                description="Creates a new simulations resource.",
            ),
            get_operation_info(
                get_simulations,
                description="Batch retrieves simulations by IDs.",
            ),
            get_operation_info(
                search_simulations,
                description="Filtered paginated search returning matching simulations.",
            ),
        ],
    )
