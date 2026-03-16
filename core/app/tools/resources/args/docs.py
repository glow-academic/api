"""Args resource documentation."""

import asyncpg

from app.infra.docs.get_operation_info import get_operation_info
from app.infra.docs.get_table_info import get_table_info
from app.infra.docs.types import DocsResponse
from app.tools.resources.args.create import create_arg
from app.tools.resources.args.get import get_args
from app.tools.resources.args.search import search_args


async def get_args_docs(conn: asyncpg.Connection) -> DocsResponse:
    """Get full documentation for the args resource."""
    resource_table = await get_table_info(conn, "args_resource")
    tables = [t for t in [resource_table] if t is not None]

    return DocsResponse(
        name="args",
        type="resource",
        description="Tool argument definitions with name, type, and description.",
        tables=tables,
        operations=[
            get_operation_info(
                create_arg,
                description="Creates a new args resource.",
            ),
            get_operation_info(
                get_args,
                description="Batch retrieves args by IDs.",
            ),
            get_operation_info(
                search_args,
                description="Filtered paginated search returning matching args.",
            ),
        ],
    )
