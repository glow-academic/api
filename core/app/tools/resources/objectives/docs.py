"""Objectives resource documentation."""

import asyncpg

from app.infra.docs.get_operation_info import get_operation_info
from app.infra.docs.get_table_info import get_table_info
from app.infra.docs.types import DocsResponse
from app.tools.resources.objectives.create import create_objective
from app.tools.resources.objectives.get import get_objectives
from app.tools.resources.objectives.search import search_objectives


async def get_objectives_docs(conn: asyncpg.Connection) -> DocsResponse:
    """Get full documentation for the objectives resource."""
    resource_table = await get_table_info(conn, "objectives_resource")
    tables = [t for t in [resource_table] if t is not None]

    return DocsResponse(
        name="objectives",
        type="resource",
        description="Learning objectives for scenario configurations.",
        tables=tables,
        operations=[
            get_operation_info(
                create_objective,
                description="Creates a new objectives resource.",
            ),
            get_operation_info(
                get_objectives,
                description="Batch retrieves objectives by IDs.",
            ),
            get_operation_info(
                search_objectives,
                description="Filtered paginated search returning matching objectives.",
            ),
        ],
    )
