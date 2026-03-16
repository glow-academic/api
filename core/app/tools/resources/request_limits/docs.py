"""Request Limits resource documentation."""

import asyncpg

from app.infra.docs.get_operation_info import get_operation_info
from app.infra.docs.get_table_info import get_table_info
from app.infra.docs.types import DocsResponse
from app.tools.resources.request_limits.create import create_request_limit
from app.tools.resources.request_limits.get import get_request_limits
from app.tools.resources.request_limits.search import search_request_limits


async def get_request_limits_docs(conn: asyncpg.Connection) -> DocsResponse:
    """Get full documentation for the request limits resource."""
    resource_table = await get_table_info(conn, "request_limits_resource")
    tables = [t for t in [resource_table] if t is not None]

    return DocsResponse(
        name="request_limits",
        type="resource",
        description="API request rate limit configurations.",
        tables=tables,
        operations=[
            get_operation_info(
                create_request_limit,
                description="Creates a new request limits resource.",
            ),
            get_operation_info(
                get_request_limits,
                description="Batch retrieves request limits by IDs.",
            ),
            get_operation_info(
                search_request_limits,
                description="Filtered paginated search returning matching request limits.",
            ),
        ],
    )
