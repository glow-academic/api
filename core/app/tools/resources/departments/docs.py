"""Departments resource documentation."""

import asyncpg

from app.infra.docs.get_operation_info import get_operation_info
from app.infra.docs.get_table_info import get_table_info
from app.infra.docs.types import DocsResponse
from app.tools.resources.departments.create import create_department
from app.tools.resources.departments.get import get_departments
from app.tools.resources.departments.search import search_departments


async def get_departments_docs(conn: asyncpg.Connection) -> DocsResponse:
    """Get full documentation for the departments resource."""
    resource_table = await get_table_info(conn, "departments_resource")
    tables = [t for t in [resource_table] if t is not None]

    return DocsResponse(
        name="departments",
        type="resource",
        description="Department reference IDs linking to department artifacts.",
        tables=tables,
        operations=[
            get_operation_info(
                create_department,
                description="Creates a new departments resource.",
            ),
            get_operation_info(
                get_departments,
                description="Batch retrieves departments by IDs.",
            ),
            get_operation_info(
                search_departments,
                description="Filtered paginated search returning matching departments.",
            ),
        ],
    )
