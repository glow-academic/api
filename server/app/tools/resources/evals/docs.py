"""Evals resource documentation."""

import asyncpg

from app.infra.docs.get_operation_info import get_operation_info
from app.infra.docs.get_table_info import get_table_info
from app.infra.docs.types import DocsResponse
from app.tools.resources.evals.create import create_eval
from app.tools.resources.evals.get import get_evals
from app.tools.resources.evals.search import search_evals


async def get_evals_docs(conn: asyncpg.Connection) -> DocsResponse:
    """Get full documentation for the evals resource."""
    resource_table = await get_table_info(conn, "evals_resource")
    tables = [t for t in [resource_table] if t is not None]

    return DocsResponse(
        name="evals",
        type="resource",
        description="Eval reference IDs linking to eval artifacts.",
        tables=tables,
        operations=[
            get_operation_info(
                create_eval,
                description="Creates a new evals resource.",
            ),
            get_operation_info(
                get_evals,
                description="Batch retrieves evals by IDs.",
            ),
            get_operation_info(
                search_evals,
                description="Filtered paginated search returning matching evals.",
            ),
        ],
    )
