"""Auths resource documentation."""

import asyncpg

from app.infra.docs.get_operation_info import get_operation_info
from app.infra.docs.get_table_info import get_table_info
from app.infra.docs.types import DocsResponse
from app.tools.resources.auths.create import create_auth
from app.tools.resources.auths.get import get_auths
from app.tools.resources.auths.search import search_auths


async def get_auths_docs(conn: asyncpg.Connection) -> DocsResponse:
    """Get full documentation for the auths resource."""
    resource_table = await get_table_info(conn, "auths_resource")
    tables = [t for t in [resource_table] if t is not None]

    return DocsResponse(
        name="auths",
        type="resource",
        description="Authentication reference IDs linking to auth artifacts.",
        tables=tables,
        operations=[
            get_operation_info(
                create_auth,
                description="Creates a new auths resource.",
            ),
            get_operation_info(
                get_auths,
                description="Batch retrieves auths by IDs.",
            ),
            get_operation_info(
                search_auths,
                description="Filtered paginated search returning matching auths.",
            ),
        ],
    )
