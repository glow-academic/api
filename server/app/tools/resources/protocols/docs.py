"""Protocols resource documentation."""

import asyncpg

from app.infra.docs.get_operation_info import get_operation_info
from app.infra.docs.get_table_info import get_table_info
from app.infra.docs.types import DocsResponse
from app.tools.resources.protocols.create import create_protocol
from app.tools.resources.protocols.get import get_protocols
from app.tools.resources.protocols.search import search_protocols


async def get_protocols_docs(conn: asyncpg.Connection) -> DocsResponse:
    """Get full documentation for the protocols resource."""
    resource_table = await get_table_info(conn, "protocols_resource")
    tables = [t for t in [resource_table] if t is not None]

    return DocsResponse(
        name="protocols",
        type="resource",
        description="Authentication protocol definitions.",
        tables=tables,
        operations=[
            get_operation_info(
                create_protocol,
                description="Creates a new protocols resource.",
            ),
            get_operation_info(
                get_protocols,
                description="Batch retrieves protocols by IDs.",
            ),
            get_operation_info(
                search_protocols,
                description="Filtered paginated search returning matching protocols.",
            ),
        ],
    )
