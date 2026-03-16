"""Fields resource documentation."""

import asyncpg

from app.infra.docs.get_operation_info import get_operation_info
from app.infra.docs.get_table_info import get_table_info
from app.infra.docs.types import DocsResponse
from app.tools.resources.fields.create import create_field
from app.tools.resources.fields.get import get_fields
from app.tools.resources.fields.search import search_fields


async def get_fields_docs(conn: asyncpg.Connection) -> DocsResponse:
    """Get full documentation for the fields resource."""
    resource_table = await get_table_info(conn, "fields_resource")
    tables = [t for t in [resource_table] if t is not None]

    return DocsResponse(
        name="fields",
        type="resource",
        description="Field reference IDs linking to field artifacts.",
        tables=tables,
        operations=[
            get_operation_info(
                create_field,
                description="Creates a new fields resource.",
            ),
            get_operation_info(
                get_fields,
                description="Batch retrieves fields by IDs.",
            ),
            get_operation_info(
                search_fields,
                description="Filtered paginated search returning matching fields.",
            ),
        ],
    )
