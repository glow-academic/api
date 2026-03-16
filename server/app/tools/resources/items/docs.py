"""Items resource documentation."""

import asyncpg

from app.infra.docs.get_operation_info import get_operation_info
from app.infra.docs.get_table_info import get_table_info
from app.infra.docs.types import DocsResponse
from app.tools.resources.items.create import create_item
from app.tools.resources.items.get import get_items
from app.tools.resources.items.search import search_items


async def get_items_docs(conn: asyncpg.Connection) -> DocsResponse:
    """Get full documentation for the items resource."""
    resource_table = await get_table_info(conn, "items_resource")
    tables = [t for t in [resource_table] if t is not None]

    return DocsResponse(
        name="items",
        type="resource",
        description="Authentication items for auth configurations.",
        tables=tables,
        operations=[
            get_operation_info(
                create_item,
                description="Creates a new items resource.",
            ),
            get_operation_info(
                get_items,
                description="Batch retrieves items by IDs.",
            ),
            get_operation_info(
                search_items,
                description="Filtered paginated search returning matching items.",
            ),
        ],
    )
