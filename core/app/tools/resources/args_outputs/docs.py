"""Args Outputs resource documentation."""

import asyncpg

from app.infra.docs.get_operation_info import get_operation_info
from app.infra.docs.get_table_info import get_table_info
from app.infra.docs.types import DocsResponse
from app.tools.resources.args_outputs.create import create_args_output
from app.tools.resources.args_outputs.get import get_args_outputs
from app.tools.resources.args_outputs.search import search_args_outputs


async def get_args_outputs_docs(conn: asyncpg.Connection) -> DocsResponse:
    """Get full documentation for the args outputs resource."""
    resource_table = await get_table_info(conn, "args_outputs_resource")
    tables = [t for t in [resource_table] if t is not None]

    return DocsResponse(
        name="args_outputs",
        type="resource",
        description="Tool argument output definitions.",
        tables=tables,
        operations=[
            get_operation_info(
                create_args_output,
                description="Creates a new args outputs resource.",
            ),
            get_operation_info(
                get_args_outputs,
                description="Batch retrieves args outputs by IDs.",
            ),
            get_operation_info(
                search_args_outputs,
                description="Filtered paginated search returning matching args outputs.",
            ),
        ],
    )
