"""Parameter artifact documentation."""

import asyncpg

from app.infra.docs.get_operation_info import get_operation_info
from app.infra.docs.get_table_info import get_table_info
from app.infra.docs.types import DocsResponse
from app.tools.artifacts.parameter.create import create_parameter
from app.tools.artifacts.parameter.delete import delete_parameters
from app.tools.artifacts.parameter.get import get_parameters
from app.tools.artifacts.parameter.search import search_parameters
from app.tools.artifacts.parameter.update import update_parameter


async def get_parameter_docs(conn: asyncpg.Connection) -> DocsResponse:
    """Get full documentation for the parameter artifact."""
    artifact_table = await get_table_info(conn, "parameter_artifact")
    tables = [t for t in [artifact_table] if t is not None]

    return DocsResponse(
        name="parameter",
        type="artifact",
        description=(
            "Parameters define configurable form structures containing fields. "
            "Each parameter links to resources (names, descriptions, departments, fields) "
            "via junction tables."
        ),
        tables=tables,
        operations=[
            get_operation_info(
                create_parameter,
                description="Creates a new parameter artifact with optional resource links.",
            ),
            get_operation_info(
                update_parameter,
                description="Updates an existing parameter's resource links.",
            ),
            get_operation_info(
                get_parameters,
                description="Batch retrieves parameters by IDs with optional junction data.",
            ),
            get_operation_info(
                search_parameters,
                description="Filtered paginated search returning matching parameter IDs.",
            ),
            get_operation_info(
                delete_parameters,
                description="Deletes parameters by IDs. Supports soft delete (active=false) or hard delete (cascade).",
            ),
        ],
    )
