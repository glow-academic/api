"""Descriptions resource documentation."""

import asyncpg

from app.infra.docs.get_operation_info import get_operation_info
from app.infra.docs.get_table_info import get_table_info
from app.infra.docs.types import DocsResponse
from app.tools.resources.descriptions.create import create_description
from app.tools.resources.descriptions.get import get_descriptions
from app.tools.resources.descriptions.search import search_descriptions


async def get_descriptions_docs(conn: asyncpg.Connection) -> DocsResponse:
    """Get full documentation for the descriptions resource."""
    resource_table = await get_table_info(conn, "descriptions_resource")
    tables = [t for t in [resource_table] if t is not None]

    return DocsResponse(
        name="descriptions",
        type="resource",
        description="Text descriptions shared across artifacts.",
        tables=tables,
        operations=[
            get_operation_info(
                create_description,
                description="Creates a new descriptions resource.",
            ),
            get_operation_info(
                get_descriptions,
                description="Batch retrieves descriptions by IDs.",
            ),
            get_operation_info(
                search_descriptions,
                description="Filtered paginated search returning matching descriptions.",
            ),
        ],
    )
