"""Department artifact documentation."""

import asyncpg

from app.infra.docs.get_operation_info import get_operation_info
from app.infra.docs.get_table_info import get_table_info
from app.infra.docs.types import DocsResponse
from app.tools.artifacts.department.create import create_department
from app.tools.artifacts.department.delete import delete_departments
from app.tools.artifacts.department.get import get_departments
from app.tools.artifacts.department.search import search_departments
from app.tools.artifacts.department.update import update_department


async def get_department_docs(conn: asyncpg.Connection) -> DocsResponse:
    """Get full documentation for the department artifact."""
    artifact_table = await get_table_info(conn, "department_artifact")
    tables = [t for t in [artifact_table] if t is not None]

    return DocsResponse(
        name="department",
        type="artifact",
        description=(
            "Departments organize artifacts and users into groups for access control. "
            "Each department links to resources (names, descriptions, settings) "
            "via junction tables."
        ),
        tables=tables,
        operations=[
            get_operation_info(
                create_department,
                description="Creates a new department artifact with optional resource links.",
            ),
            get_operation_info(
                update_department,
                description="Updates an existing department's resource links.",
            ),
            get_operation_info(
                get_departments,
                description="Batch retrieves departments by IDs with optional junction data.",
            ),
            get_operation_info(
                search_departments,
                description="Filtered paginated search returning matching department IDs.",
            ),
            get_operation_info(
                delete_departments,
                description="Deletes departments by IDs. Supports soft delete (active=false) or hard delete (cascade).",
            ),
        ],
    )
