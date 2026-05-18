"""Simulation Availability resource documentation."""

import asyncpg

from app.infra.docs.get_operation_info import get_operation_info
from app.infra.docs.get_table_info import get_table_info
from app.infra.docs.types import DocsResponse
from app.tools.resources.simulation_availability.create import (
    create_simulation_availability,
)
from app.tools.resources.simulation_availability.get import (
    get_simulation_availability,
)
from app.tools.resources.simulation_availability.search import (
    search_simulation_availability,
)


async def get_simulation_availability_docs(conn: asyncpg.Connection) -> DocsResponse:
    """Get full documentation for the simulation availability resource."""
    resource_table = await get_table_info(conn, "simulation_availability_resource")
    tables = [t for t in [resource_table] if t is not None]

    return DocsResponse(
        name="simulation_availability",
        type="resource",
        description="Simulation availability schedule configurations.",
        tables=tables,
        operations=[
            get_operation_info(
                create_simulation_availability,
                description="Creates a new simulation availability resource.",
            ),
            get_operation_info(
                get_simulation_availability,
                description="Batch retrieves simulation availability by IDs.",
            ),
            get_operation_info(
                search_simulation_availability,
                description="Filtered paginated search returning matching simulation availability.",
            ),
        ],
    )
