"""Scenario Time Limits resource documentation."""

import asyncpg

from app.infra.docs.get_operation_info import get_operation_info
from app.infra.docs.get_table_info import get_table_info
from app.infra.docs.types import DocsResponse
from app.tools.resources.scenario_time_limits.create import (
    create_scenario_time_limit,
)
from app.tools.resources.scenario_time_limits.get import (
    get_scenario_time_limits,
)
from app.tools.resources.scenario_time_limits.search import (
    search_scenario_time_limits,
)


async def get_scenario_time_limits_docs(conn: asyncpg.Connection) -> DocsResponse:
    """Get full documentation for the scenario time limits resource."""
    resource_table = await get_table_info(conn, "scenario_time_limits_resource")
    tables = [t for t in [resource_table] if t is not None]

    return DocsResponse(
        name="scenario_time_limits",
        type="resource",
        description="Time limit settings for simulation scenarios.",
        tables=tables,
        operations=[
            get_operation_info(
                create_scenario_time_limit,
                description="Creates a new scenario time limits resource.",
            ),
            get_operation_info(
                get_scenario_time_limits,
                description="Batch retrieves scenario time limits by IDs.",
            ),
            get_operation_info(
                search_scenario_time_limits,
                description="Filtered paginated search returning matching scenario time limits.",
            ),
        ],
    )
