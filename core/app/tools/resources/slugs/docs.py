"""Slugs resource documentation."""

import asyncpg

from app.infra.docs.get_operation_info import get_operation_info
from app.infra.docs.get_table_info import get_table_info
from app.infra.docs.types import DocsResponse
from app.tools.resources.slugs.create import create_slug
from app.tools.resources.slugs.get import get_slugs
from app.tools.resources.slugs.search import search_slugs


async def get_slugs_docs(conn: asyncpg.Connection) -> DocsResponse:
    """Get full documentation for the slugs resource."""
    resource_table = await get_table_info(conn, "slugs_resource")
    tables = [t for t in [resource_table] if t is not None]

    return DocsResponse(
        name="slugs",
        type="resource",
        description="URL slug identifiers for auth configurations.",
        tables=tables,
        operations=[
            get_operation_info(
                create_slug,
                description="Creates a new slugs resource.",
            ),
            get_operation_info(
                get_slugs,
                description="Batch retrieves slugs by IDs.",
            ),
            get_operation_info(
                search_slugs,
                description="Filtered paginated search returning matching slugs.",
            ),
        ],
    )
