"""Keys resource documentation."""

import asyncpg

from app.infra.docs.get_operation_info import get_operation_info
from app.infra.docs.get_table_info import get_table_info
from app.infra.docs.types import DocsResponse
from app.tools.resources.keys.create import create_key
from app.tools.resources.keys.get import get_keys
from app.tools.resources.keys.search import search_keys


async def get_keys_docs(conn: asyncpg.Connection) -> DocsResponse:
    """Get full documentation for the keys resource."""
    resource_table = await get_table_info(conn, "keys_resource")
    tables = [t for t in [resource_table] if t is not None]

    return DocsResponse(
        name="keys",
        type="resource",
        description="API keys for provider authentication.",
        tables=tables,
        operations=[
            get_operation_info(
                create_key,
                description="Creates a new keys resource.",
            ),
            get_operation_info(
                get_keys,
                description="Batch retrieves keys by IDs.",
            ),
            get_operation_info(
                search_keys,
                description="Filtered paginated search returning matching keys.",
            ),
        ],
    )
