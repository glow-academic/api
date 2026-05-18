"""Scenario Rubrics resource documentation."""

import asyncpg

from app.infra.docs.get_operation_info import get_operation_info
from app.infra.docs.get_table_info import get_table_info
from app.infra.docs.types import DocsResponse
from app.tools.resources.scenario_rubrics.create import create_scenario_rubric
from app.tools.resources.scenario_rubrics.get import get_scenario_rubrics
from app.tools.resources.scenario_rubrics.search import (
    search_scenario_rubrics,
)


async def get_scenario_rubrics_docs(conn: asyncpg.Connection) -> DocsResponse:
    """Get full documentation for the scenario rubrics resource."""
    resource_table = await get_table_info(conn, "scenario_rubrics_resource")
    tables = [t for t in [resource_table] if t is not None]

    return DocsResponse(
        name="scenario_rubrics",
        type="resource",
        description="Scenario-rubric associations for simulation scoring.",
        tables=tables,
        operations=[
            get_operation_info(
                create_scenario_rubric,
                description="Creates a new scenario rubrics resource.",
            ),
            get_operation_info(
                get_scenario_rubrics,
                description="Batch retrieves scenario rubrics by IDs.",
            ),
            get_operation_info(
                search_scenario_rubrics,
                description="Filtered paginated search returning matching scenario rubrics.",
            ),
        ],
    )
