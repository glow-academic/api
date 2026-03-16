"""Values resource documentation."""

import asyncpg

from app.infra.docs.get_operation_info import get_operation_info
from app.infra.docs.get_table_info import get_table_info
from app.infra.docs.types import DocsResponse
from app.tools.resources.values.create import create_value
from app.tools.resources.values.get import get_values
from app.tools.resources.values.search import search_values


async def get_values_docs(conn: asyncpg.Connection) -> DocsResponse:
    """Get full documentation for the values resource."""
    resource_table = await get_table_info(conn, "values_resource")
    tables = [t for t in [resource_table] if t is not None]

    return DocsResponse(
        name="values",
        type="resource",
        description="Key-value configuration entries for models and providers.",
        tables=tables,
        operations=[
            get_operation_info(
                create_value,
                description="Creates a new values resource.",
            ),
            get_operation_info(
                get_values,
                description="Batch retrieves values by IDs.",
            ),
            get_operation_info(
                search_values,
                description="Filtered paginated search returning matching values.",
            ),
        ],
    )
