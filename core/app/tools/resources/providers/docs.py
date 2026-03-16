"""Providers resource documentation."""

import asyncpg

from app.infra.docs.get_operation_info import get_operation_info
from app.infra.docs.get_table_info import get_table_info
from app.infra.docs.types import DocsResponse
from app.tools.resources.providers.create import create_provider
from app.tools.resources.providers.get import get_providers
from app.tools.resources.providers.search import search_providers


async def get_providers_docs(conn: asyncpg.Connection) -> DocsResponse:
    """Get full documentation for the providers resource."""
    resource_table = await get_table_info(conn, "providers_resource")
    tables = [t for t in [resource_table] if t is not None]

    return DocsResponse(
        name="providers",
        type="resource",
        description="Provider reference IDs linking to provider artifacts.",
        tables=tables,
        operations=[
            get_operation_info(
                create_provider,
                description="Creates a new providers resource.",
            ),
            get_operation_info(
                get_providers,
                description="Batch retrieves providers by IDs.",
            ),
            get_operation_info(
                search_providers,
                description="Filtered paginated search returning matching providers.",
            ),
        ],
    )
