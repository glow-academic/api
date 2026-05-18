"""Qualities resource documentation."""

import asyncpg

from app.infra.docs.get_operation_info import get_operation_info
from app.infra.docs.get_table_info import get_table_info
from app.infra.docs.types import DocsResponse
from app.tools.resources.qualities.create import create_quality
from app.tools.resources.qualities.get import get_qualities
from app.tools.resources.qualities.search import search_qualities


async def get_qualities_docs(conn: asyncpg.Connection) -> DocsResponse:
    """Get full documentation for the qualities resource."""
    resource_table = await get_table_info(conn, "qualities_resource")
    tables = [t for t in [resource_table] if t is not None]

    return DocsResponse(
        name="qualities",
        type="resource",
        description="Quality level definitions for model capabilities.",
        tables=tables,
        operations=[
            get_operation_info(
                create_quality,
                description="Creates a new qualities resource.",
            ),
            get_operation_info(
                get_qualities,
                description="Batch retrieves qualities by IDs.",
            ),
            get_operation_info(
                search_qualities,
                description="Filtered paginated search returning matching qualities.",
            ),
        ],
    )
