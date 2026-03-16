"""Parameters resource documentation."""

import asyncpg

from app.infra.docs.get_operation_info import get_operation_info
from app.infra.docs.get_table_info import get_table_info
from app.infra.docs.types import DocsResponse
from app.tools.resources.parameters.create import create_parameter
from app.tools.resources.parameters.get import get_parameters
from app.tools.resources.parameters.search import search_parameters


async def get_parameters_docs(conn: asyncpg.Connection) -> DocsResponse:
    """Get full documentation for the parameters resource."""
    resource_table = await get_table_info(conn, "parameters_resource")
    tables = [t for t in [resource_table] if t is not None]

    return DocsResponse(
        name="parameters",
        type="resource",
        description="Parameter reference IDs linking to parameter artifacts.",
        tables=tables,
        operations=[
            get_operation_info(
                create_parameter,
                description="Creates a new parameters resource.",
            ),
            get_operation_info(
                get_parameters,
                description="Batch retrieves parameters by IDs.",
            ),
            get_operation_info(
                search_parameters,
                description="Filtered paginated search returning matching parameters.",
            ),
        ],
    )
