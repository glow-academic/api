"""Provider Keys resource documentation."""

import asyncpg

from app.infra.docs.get_operation_info import get_operation_info
from app.infra.docs.get_table_info import get_table_info
from app.infra.docs.types import DocsResponse
from app.tools.resources.provider_keys.create import create_provider_key
from app.tools.resources.provider_keys.get import get_provider_keys
from app.tools.resources.provider_keys.search import search_provider_keys


async def get_provider_keys_docs(conn: asyncpg.Connection) -> DocsResponse:
    """Get full documentation for the provider keys resource."""
    resource_table = await get_table_info(conn, "provider_keys_resource")
    tables = [t for t in [resource_table] if t is not None]

    return DocsResponse(
        name="provider_keys",
        type="resource",
        description="Provider API key configurations for settings.",
        tables=tables,
        operations=[
            get_operation_info(
                create_provider_key,
                description="Creates a new provider keys resource.",
            ),
            get_operation_info(
                get_provider_keys,
                description="Batch retrieves provider keys by IDs.",
            ),
            get_operation_info(
                search_provider_keys,
                description="Filtered paginated search returning matching provider keys.",
            ),
        ],
    )
