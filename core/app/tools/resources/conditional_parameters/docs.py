"""Conditional Parameters resource documentation."""

import asyncpg

from app.infra.docs.get_operation_info import get_operation_info
from app.infra.docs.get_table_info import get_table_info
from app.infra.docs.types import DocsResponse
from app.tools.resources.conditional_parameters.create import (
    create_conditional_parameter,
)
from app.tools.resources.conditional_parameters.get import (
    get_conditional_parameters,
)
from app.tools.resources.conditional_parameters.search import (
    search_conditional_parameters,
)


async def get_conditional_parameters_docs(conn: asyncpg.Connection) -> DocsResponse:
    """Get full documentation for the conditional parameters resource."""
    resource_table = await get_table_info(conn, "conditional_parameters_resource")
    tables = [t for t in [resource_table] if t is not None]

    return DocsResponse(
        name="conditional_parameters",
        type="resource",
        description="Conditional parameter links for field dependencies.",
        tables=tables,
        operations=[
            get_operation_info(
                create_conditional_parameter,
                description="Creates a new conditional parameters resource.",
            ),
            get_operation_info(
                get_conditional_parameters,
                description="Batch retrieves conditional parameters by IDs.",
            ),
            get_operation_info(
                search_conditional_parameters,
                description="Filtered paginated search returning matching conditional parameters.",
            ),
        ],
    )
