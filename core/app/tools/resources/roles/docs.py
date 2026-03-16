"""Roles resource documentation."""

import asyncpg

from app.infra.docs.get_operation_info import get_operation_info
from app.infra.docs.get_table_info import get_table_info
from app.infra.docs.types import DocsResponse
from app.tools.resources.roles.create import create_role
from app.tools.resources.roles.get import get_roles
from app.tools.resources.roles.search import search_roles


async def get_roles_docs(conn: asyncpg.Connection) -> DocsResponse:
    """Get full documentation for the roles resource."""
    resource_table = await get_table_info(conn, "roles_resource")
    tables = [t for t in [resource_table] if t is not None]

    return DocsResponse(
        name="roles",
        type="resource",
        description="User role assignments for profile permissions.",
        tables=tables,
        operations=[
            get_operation_info(
                create_role,
                description="Creates a new roles resource.",
            ),
            get_operation_info(
                get_roles,
                description="Batch retrieves roles by IDs.",
            ),
            get_operation_info(
                search_roles,
                description="Filtered paginated search returning matching roles.",
            ),
        ],
    )
