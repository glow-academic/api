"""Icons resource documentation."""

import asyncpg

from app.infra.docs.get_operation_info import get_operation_info
from app.infra.docs.get_table_info import get_table_info
from app.infra.docs.types import DocsResponse
from app.tools.resources.icons.create import create_icon
from app.tools.resources.icons.get import get_icons
from app.tools.resources.icons.search import search_icons


async def get_icons_docs(conn: asyncpg.Connection) -> DocsResponse:
    """Get full documentation for the icons resource."""
    resource_table = await get_table_info(conn, "icons_resource")
    tables = [t for t in [resource_table] if t is not None]

    return DocsResponse(
        name="icons",
        type="resource",
        description="Icon identifiers for persona visual representation.",
        tables=tables,
        operations=[
            get_operation_info(
                create_icon,
                description="Creates a new icons resource.",
            ),
            get_operation_info(
                get_icons,
                description="Batch retrieves icons by IDs.",
            ),
            get_operation_info(
                search_icons,
                description="Filtered paginated search returning matching icons.",
            ),
        ],
    )
