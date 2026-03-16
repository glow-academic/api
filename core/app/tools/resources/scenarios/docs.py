"""Scenarios resource documentation."""

import asyncpg

from app.infra.docs.get_operation_info import get_operation_info
from app.infra.docs.get_table_info import get_table_info
from app.infra.docs.types import DocsResponse
from app.tools.resources.scenarios.create import create_scenario
from app.tools.resources.scenarios.get import get_scenarios
from app.tools.resources.scenarios.search import search_scenarios


async def get_scenarios_docs(conn: asyncpg.Connection) -> DocsResponse:
    """Get full documentation for the scenarios resource."""
    resource_table = await get_table_info(conn, "scenarios_resource")
    tables = [t for t in [resource_table] if t is not None]

    return DocsResponse(
        name="scenarios",
        type="resource",
        description="Scenario reference IDs linking to scenario artifacts.",
        tables=tables,
        operations=[
            get_operation_info(
                create_scenario,
                description="Creates a new scenarios resource.",
            ),
            get_operation_info(
                get_scenarios,
                description="Batch retrieves scenarios by IDs.",
            ),
            get_operation_info(
                search_scenarios,
                description="Filtered paginated search returning matching scenarios.",
            ),
        ],
    )
