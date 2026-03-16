"""Options resource documentation."""

import asyncpg

from app.infra.docs.get_operation_info import get_operation_info
from app.infra.docs.get_table_info import get_table_info
from app.infra.docs.types import DocsResponse
from app.tools.resources.options.create import create_option
from app.tools.resources.options.get import get_options
from app.tools.resources.options.search import search_options


async def get_options_docs(conn: asyncpg.Connection) -> DocsResponse:
    """Get full documentation for the options resource."""
    resource_table = await get_table_info(conn, "options_resource")
    tables = [t for t in [resource_table] if t is not None]

    return DocsResponse(
        name="options",
        type="resource",
        description="Multiple choice options for scenario questions.",
        tables=tables,
        operations=[
            get_operation_info(
                create_option,
                description="Creates a new options resource.",
            ),
            get_operation_info(
                get_options,
                description="Batch retrieves options by IDs.",
            ),
            get_operation_info(
                search_options,
                description="Filtered paginated search returning matching options.",
            ),
        ],
    )
