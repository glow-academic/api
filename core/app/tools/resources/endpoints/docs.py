"""Endpoints resource documentation."""

import asyncpg

from app.infra.docs.get_operation_info import get_operation_info
from app.infra.docs.get_table_info import get_table_info
from app.infra.docs.types import DocsResponse
from app.tools.resources.endpoints.create import create_endpoint
from app.tools.resources.endpoints.get import get_endpoints
from app.tools.resources.endpoints.search import search_endpoints


async def get_endpoints_docs(conn: asyncpg.Connection) -> DocsResponse:
    """Get full documentation for the endpoints resource."""
    resource_table = await get_table_info(conn, "endpoints_resource")
    tables = [t for t in [resource_table] if t is not None]

    return DocsResponse(
        name="endpoints",
        type="resource",
        description="API endpoint URLs for provider configurations.",
        tables=tables,
        operations=[
            get_operation_info(
                create_endpoint,
                description="Creates a new endpoints resource.",
            ),
            get_operation_info(
                get_endpoints,
                description="Batch retrieves endpoints by IDs.",
            ),
            get_operation_info(
                search_endpoints,
                description="Filtered paginated search returning matching endpoints.",
            ),
        ],
    )
