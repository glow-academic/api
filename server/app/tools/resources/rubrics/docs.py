"""Rubrics resource documentation."""

import asyncpg

from app.infra.docs.get_operation_info import get_operation_info
from app.infra.docs.get_table_info import get_table_info
from app.infra.docs.types import DocsResponse
from app.tools.resources.rubrics.create import create_rubric
from app.tools.resources.rubrics.get import get_rubrics
from app.tools.resources.rubrics.search import search_rubrics


async def get_rubrics_docs(conn: asyncpg.Connection) -> DocsResponse:
    """Get full documentation for the rubrics resource."""
    resource_table = await get_table_info(conn, "rubrics_resource")
    tables = [t for t in [resource_table] if t is not None]

    return DocsResponse(
        name="rubrics",
        type="resource",
        description="Rubric reference IDs linking to rubric artifacts.",
        tables=tables,
        operations=[
            get_operation_info(
                create_rubric,
                description="Creates a new rubrics resource.",
            ),
            get_operation_info(
                get_rubrics,
                description="Batch retrieves rubrics by IDs.",
            ),
            get_operation_info(
                search_rubrics,
                description="Filtered paginated search returning matching rubrics.",
            ),
        ],
    )
