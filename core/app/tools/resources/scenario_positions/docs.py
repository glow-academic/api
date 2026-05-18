"""Scenario Positions resource documentation."""

import asyncpg

from app.infra.docs.get_operation_info import get_operation_info
from app.infra.docs.get_table_info import get_table_info
from app.infra.docs.types import DocsResponse
from app.tools.resources.scenario_positions.create import (
    create_scenario_position,
)
from app.tools.resources.scenario_positions.get import get_scenario_positions
from app.tools.resources.scenario_positions.search import (
    search_scenario_positions,
)


async def get_scenario_positions_docs(conn: asyncpg.Connection) -> DocsResponse:
    """Get full documentation for the scenario positions resource."""
    resource_table = await get_table_info(conn, "scenario_positions_resource")
    tables = [t for t in [resource_table] if t is not None]

    return DocsResponse(
        name="scenario_positions",
        type="resource",
        description="Scenario position orderings within simulations.",
        tables=tables,
        operations=[
            get_operation_info(
                create_scenario_position,
                description="Creates a new scenario positions resource.",
            ),
            get_operation_info(
                get_scenario_positions,
                description="Batch retrieves scenario positions by IDs.",
            ),
            get_operation_info(
                search_scenario_positions,
                description="Filtered paginated search returning matching scenario positions.",
            ),
        ],
    )
