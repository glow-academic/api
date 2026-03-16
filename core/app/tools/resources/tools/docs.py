"""Tools resource documentation."""

import asyncpg

from app.infra.docs.get_operation_info import get_operation_info
from app.infra.docs.get_table_info import get_table_info
from app.infra.docs.types import DocsResponse
from app.tools.resources.tools.create import create_tool
from app.tools.resources.tools.get import get_tools
from app.tools.resources.tools.search import search_tools


async def get_tools_docs(conn: asyncpg.Connection) -> DocsResponse:
    """Get full documentation for the tools resource."""
    resource_table = await get_table_info(conn, "tools_resource")
    tables = [t for t in [resource_table] if t is not None]

    return DocsResponse(
        name="tools",
        type="resource",
        description="Tool reference IDs linking to tool artifacts.",
        tables=tables,
        operations=[
            get_operation_info(
                create_tool,
                description="Creates a new tools resource.",
            ),
            get_operation_info(
                get_tools,
                description="Batch retrieves tools by IDs.",
            ),
            get_operation_info(
                search_tools,
                description="Filtered paginated search returning matching tools.",
            ),
        ],
    )
