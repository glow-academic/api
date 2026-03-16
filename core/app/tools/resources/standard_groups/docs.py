"""Standard Groups resource documentation."""

import asyncpg

from app.infra.docs.get_operation_info import get_operation_info
from app.infra.docs.get_table_info import get_table_info
from app.infra.docs.types import DocsResponse
from app.tools.resources.standard_groups.create import create_standard_group
from app.tools.resources.standard_groups.get import get_standard_groups
from app.tools.resources.standard_groups.search import search_standard_groups


async def get_standard_groups_docs(conn: asyncpg.Connection) -> DocsResponse:
    """Get full documentation for the standard groups resource."""
    resource_table = await get_table_info(conn, "standard_groups_resource")
    tables = [t for t in [resource_table] if t is not None]

    return DocsResponse(
        name="standard_groups",
        type="resource",
        description="Standard groupings for rubric organization.",
        tables=tables,
        operations=[
            get_operation_info(
                create_standard_group,
                description="Creates a new standard groups resource.",
            ),
            get_operation_info(
                get_standard_groups,
                description="Batch retrieves standard groups by IDs.",
            ),
            get_operation_info(
                search_standard_groups,
                description="Filtered paginated search returning matching standard groups.",
            ),
        ],
    )
