"""Flags resource documentation."""

import asyncpg

from app.infra.docs.get_operation_info import get_operation_info
from app.infra.docs.get_table_info import get_table_info
from app.infra.docs.types import DocsResponse
from app.tools.resources.flags.create import create_flag
from app.tools.resources.flags.get import get_flags
from app.tools.resources.flags.search import search_flags


async def get_flags_docs(conn: asyncpg.Connection) -> DocsResponse:
    """Get full documentation for the flags resource."""
    resource_table = await get_table_info(conn, "flags_resource")
    tables = [t for t in [resource_table] if t is not None]

    return DocsResponse(
        name="flags",
        type="resource",
        description="Feature flags and categorization tags for artifacts.",
        tables=tables,
        operations=[
            get_operation_info(
                create_flag,
                description="Creates a new flags resource.",
            ),
            get_operation_info(
                get_flags,
                description="Batch retrieves flags by IDs.",
            ),
            get_operation_info(
                search_flags,
                description="Filtered paginated search returning matching flags.",
            ),
        ],
    )
