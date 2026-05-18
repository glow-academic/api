"""Parameter Fields resource documentation."""

import asyncpg

from app.infra.docs.get_operation_info import get_operation_info
from app.infra.docs.get_table_info import get_table_info
from app.infra.docs.types import DocsResponse
from app.tools.resources.parameter_fields.create import create_parameter_field
from app.tools.resources.parameter_fields.get import get_parameter_fields
from app.tools.resources.parameter_fields.search import (
    search_parameter_fields,
)


async def get_parameter_fields_docs(conn: asyncpg.Connection) -> DocsResponse:
    """Get full documentation for the parameter fields resource."""
    resource_table = await get_table_info(conn, "parameter_fields_resource")
    tables = [t for t in [resource_table] if t is not None]

    return DocsResponse(
        name="parameter_fields",
        type="resource",
        description="Parameter-field composite links for form structures.",
        tables=tables,
        operations=[
            get_operation_info(
                create_parameter_field,
                description="Creates a new parameter fields resource.",
            ),
            get_operation_info(
                get_parameter_fields,
                description="Batch retrieves parameter fields by IDs.",
            ),
            get_operation_info(
                search_parameter_fields,
                description="Filtered paginated search returning matching parameter fields.",
            ),
        ],
    )
