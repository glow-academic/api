"""Scenario Flags resource documentation."""

import asyncpg

from app.infra.docs.get_operation_info import get_operation_info
from app.infra.docs.get_table_info import get_table_info
from app.infra.docs.types import DocsResponse
from app.tools.resources.scenario_flags.create import create_scenario_flag
from app.tools.resources.scenario_flags.get import get_scenario_flags
from app.tools.resources.scenario_flags.search import search_scenario_flags


async def get_scenario_flags_docs(conn: asyncpg.Connection) -> DocsResponse:
    """Get full documentation for the scenario flags resource."""
    resource_table = await get_table_info(conn, "scenario_flags_resource")
    tables = [t for t in [resource_table] if t is not None]

    return DocsResponse(
        name="scenario_flags",
        type="resource",
        description="Scenario-specific flags for simulation configurations.",
        tables=tables,
        operations=[
            get_operation_info(
                create_scenario_flag,
                description="Creates a new scenario flags resource.",
            ),
            get_operation_info(
                get_scenario_flags,
                description="Batch retrieves scenario flags by IDs.",
            ),
            get_operation_info(
                search_scenario_flags,
                description="Filtered paginated search returning matching scenario flags.",
            ),
        ],
    )
