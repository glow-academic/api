"""Auth Item Keys resource documentation."""

import asyncpg

from app.infra.docs.get_operation_info import get_operation_info
from app.infra.docs.get_table_info import get_table_info
from app.infra.docs.types import DocsResponse
from app.tools.resources.auth_item_keys.create import create_auth_item_key
from app.tools.resources.auth_item_keys.get import get_auth_item_keys
from app.tools.resources.auth_item_keys.search import search_auth_item_keys


async def get_auth_item_keys_docs(conn: asyncpg.Connection) -> DocsResponse:
    """Get full documentation for the auth item keys resource."""
    resource_table = await get_table_info(conn, "auth_item_keys_resource")
    tables = [t for t in [resource_table] if t is not None]

    return DocsResponse(
        name="auth_item_keys",
        type="resource",
        description="Authentication item key configurations.",
        tables=tables,
        operations=[
            get_operation_info(
                create_auth_item_key,
                description="Creates a new auth item keys resource.",
            ),
            get_operation_info(
                get_auth_item_keys,
                description="Batch retrieves auth item keys by IDs.",
            ),
            get_operation_info(
                search_auth_item_keys,
                description="Filtered paginated search returning matching auth item keys.",
            ),
        ],
    )
