"""Scenario artifact documentation."""

import asyncpg

from app.infra.docs.get_operation_info import get_operation_info
from app.infra.docs.get_table_info import get_table_info
from app.infra.docs.types import DocsResponse
from app.tools.artifacts.scenario.create import create_scenario
from app.tools.artifacts.scenario.delete import delete_scenarios
from app.tools.artifacts.scenario.get import get_scenarios
from app.tools.artifacts.scenario.search import search_scenarios
from app.tools.artifacts.scenario.update import update_scenario


async def get_scenario_docs(conn: asyncpg.Connection) -> DocsResponse:
    """Get full documentation for the scenario artifact."""
    artifact_table = await get_table_info(conn, "scenario_artifact")
    tables = [t for t in [artifact_table] if t is not None]

    return DocsResponse(
        name="scenario",
        type="artifact",
        description=(
            "Scenarios define simulation conversation setups with personas and documents. "
            "Each scenario links to resources (names, descriptions, departments, documents, "
            "images, objectives, options, parameter_fields, personas, problem_statements, "
            "questions, videos) via junction tables."
        ),
        tables=tables,
        operations=[
            get_operation_info(
                create_scenario,
                description="Creates a new scenario artifact with optional resource links.",
            ),
            get_operation_info(
                update_scenario,
                description="Updates an existing scenario's resource links.",
            ),
            get_operation_info(
                get_scenarios,
                description="Batch retrieves scenarios by IDs with optional junction data.",
            ),
            get_operation_info(
                search_scenarios,
                description="Filtered paginated search returning matching scenario IDs.",
            ),
            get_operation_info(
                delete_scenarios,
                description="Deletes scenarios by IDs. Supports soft delete (active=false) or hard delete (cascade).",
            ),
        ],
    )
