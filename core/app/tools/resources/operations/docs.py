"""Operations resource documentation."""

import asyncpg

from app.infra.docs.get_operation_info import get_operation_info
from app.infra.docs.get_table_info import get_table_info
from app.infra.docs.types import DocsResponse
from app.tools.resources.operations.create import create_operation
from app.tools.resources.operations.get import get_operations
from app.tools.resources.operations.search import search_operations


async def get_operations_docs(conn: asyncpg.Connection) -> DocsResponse:
    """Get full documentation for the operations resource."""
    resource_table = await get_table_info(conn, "operations_resource")
    tables = [t for t in [resource_table] if t is not None]

    return DocsResponse(
        name="operations",
        type="resource",
        description="Operation type references used by tools.",
        tables=tables,
        operations=[
            get_operation_info(
                create_operation,
                description="Creates a new operations resource.",
            ),
            get_operation_info(
                get_operations,
                description="Batch retrieves operations by IDs.",
            ),
            get_operation_info(
                search_operations,
                description="Filtered paginated search returning matching operations.",
            ),
        ],
    )
