"""Names resource documentation."""

import asyncpg

from app.infra.docs.get_operation_info import get_operation_info
from app.infra.docs.get_table_info import get_table_info
from app.infra.docs.types import DocsResponse
from app.tools.resources.names.create import create_name
from app.tools.resources.names.get import get_names
from app.tools.resources.names.search import search_names


async def get_names_docs(conn: asyncpg.Connection) -> DocsResponse:
    """Get full documentation for the names resource."""
    resource_table = await get_table_info(conn, "names_resource")
    tables = [t for t in [resource_table] if t is not None]

    return DocsResponse(
        name="names",
        type="resource",
        description="Display names shared across all artifacts and resources.",
        tables=tables,
        operations=[
            get_operation_info(
                create_name,
                description="Creates a new names resource.",
            ),
            get_operation_info(
                get_names,
                description="Batch retrieves names by IDs.",
            ),
            get_operation_info(
                search_names,
                description="Filtered paginated search returning matching names.",
            ),
        ],
    )
