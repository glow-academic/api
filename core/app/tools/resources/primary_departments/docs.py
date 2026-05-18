"""Primary Departments resource documentation."""

import asyncpg

from app.infra.docs.get_operation_info import get_operation_info
from app.infra.docs.get_table_info import get_table_info
from app.infra.docs.types import DocsResponse
from app.tools.resources.primary_departments.create import (
    create_primary_department,
)
from app.tools.resources.primary_departments.get import (
    get_primary_departments,
)
from app.tools.resources.primary_departments.search import (
    search_primary_departments,
)


async def get_primary_departments_docs(conn: asyncpg.Connection) -> DocsResponse:
    """Get full documentation for the primary departments resource."""
    resource_table = await get_table_info(conn, "primary_departments_resource")
    tables = [t for t in [resource_table] if t is not None]

    return DocsResponse(
        name="primary_departments",
        type="resource",
        description="Catalog of per-profile primary-department designations; wraps a departments_resource row as the primary for a profile.",
        tables=tables,
        operations=[
            get_operation_info(
                create_primary_department,
                description="Create a primary_departments_resource row pointing at a departments_resource.",
            ),
            get_operation_info(
                get_primary_departments,
                description="Batch retrieve primary_departments by IDs.",
            ),
            get_operation_info(
                search_primary_departments,
                description="Filtered paginated search across primary_departments_resource.",
            ),
        ],
    )
