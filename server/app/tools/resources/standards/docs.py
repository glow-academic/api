"""Standards resource documentation."""

import asyncpg

from app.infra.docs.get_operation_info import get_operation_info
from app.infra.docs.get_table_info import get_table_info
from app.infra.docs.types import DocsResponse
from app.tools.resources.standards.create import create_standard
from app.tools.resources.standards.get import get_standards
from app.tools.resources.standards.search import search_standards


async def get_standards_docs(conn: asyncpg.Connection) -> DocsResponse:
    """Get full documentation for the standards resource."""
    resource_table = await get_table_info(conn, "standards_resource")
    tables = [t for t in [resource_table] if t is not None]

    return DocsResponse(
        name="standards",
        type="resource",
        description="Individual scoring standards within rubric groups.",
        tables=tables,
        operations=[
            get_operation_info(
                create_standard,
                description="Creates a new standards resource.",
            ),
            get_operation_info(
                get_standards,
                description="Batch retrieves standards by IDs.",
            ),
            get_operation_info(
                search_standards,
                description="Filtered paginated search returning matching standards.",
            ),
        ],
    )
