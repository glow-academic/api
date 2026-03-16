"""Arg Positions resource documentation."""

import asyncpg

from app.infra.docs.get_operation_info import get_operation_info
from app.infra.docs.get_table_info import get_table_info
from app.infra.docs.types import DocsResponse
from app.tools.resources.arg_positions.create import create_arg_position
from app.tools.resources.arg_positions.get import get_arg_positions
from app.tools.resources.arg_positions.search import search_arg_positions


async def get_arg_positions_docs(conn: asyncpg.Connection) -> DocsResponse:
    """Get full documentation for the arg positions resource."""
    resource_table = await get_table_info(conn, "arg_positions_resource")
    tables = [t for t in [resource_table] if t is not None]

    return DocsResponse(
        name="arg_positions",
        type="resource",
        description="Argument position orderings for tool parameters.",
        tables=tables,
        operations=[
            get_operation_info(
                create_arg_position,
                description="Creates a new arg positions resource.",
            ),
            get_operation_info(
                get_arg_positions,
                description="Batch retrieves arg positions by IDs.",
            ),
            get_operation_info(
                search_arg_positions,
                description="Filtered paginated search returning matching arg positions.",
            ),
        ],
    )
