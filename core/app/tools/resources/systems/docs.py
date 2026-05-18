"""Systems resource documentation."""

import asyncpg

from app.infra.docs.get_operation_info import get_operation_info
from app.infra.docs.get_table_info import get_table_info
from app.infra.docs.types import DocsResponse
from app.tools.resources.systems.create import create_system
from app.tools.resources.systems.get import get_systems
from app.tools.resources.systems.search import search_systems


async def get_systems_docs(conn: asyncpg.Connection) -> DocsResponse:
    """Get full documentation for the systems resource."""
    resource_table = await get_table_info(conn, "systems_resource")
    tables = [t for t in [resource_table] if t is not None]

    return DocsResponse(
        name="systems",
        type="resource",
        description="System-level configuration values for settings.",
        tables=tables,
        operations=[
            get_operation_info(
                create_system,
                description="Creates a new systems resource.",
            ),
            get_operation_info(
                get_systems,
                description="Batch retrieves systems by IDs.",
            ),
            get_operation_info(
                search_systems,
                description="Filtered paginated search returning matching systems.",
            ),
        ],
    )
