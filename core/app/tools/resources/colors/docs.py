"""Colors resource documentation."""

import asyncpg

from app.infra.docs.get_operation_info import get_operation_info
from app.infra.docs.get_table_info import get_table_info
from app.infra.docs.types import DocsResponse
from app.tools.resources.colors.create import create_color
from app.tools.resources.colors.get import get_colors
from app.tools.resources.colors.search import search_colors


async def get_colors_docs(conn: asyncpg.Connection) -> DocsResponse:
    """Get full documentation for the colors resource."""
    resource_table = await get_table_info(conn, "colors_resource")
    tables = [t for t in [resource_table] if t is not None]

    return DocsResponse(
        name="colors",
        type="resource",
        description="Color values used for branding and theming.",
        tables=tables,
        operations=[
            get_operation_info(
                create_color,
                description="Creates a new colors resource.",
            ),
            get_operation_info(
                get_colors,
                description="Batch retrieves colors by IDs.",
            ),
            get_operation_info(
                search_colors,
                description="Filtered paginated search returning matching colors.",
            ),
        ],
    )
