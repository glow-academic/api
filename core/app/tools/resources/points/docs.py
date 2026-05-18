"""Points resource documentation."""

import asyncpg

from app.infra.docs.get_operation_info import get_operation_info
from app.infra.docs.get_table_info import get_table_info
from app.infra.docs.types import DocsResponse
from app.tools.resources.points.create import create_point
from app.tools.resources.points.get import get_points
from app.tools.resources.points.search import search_points


async def get_points_docs(conn: asyncpg.Connection) -> DocsResponse:
    """Get full documentation for the points resource."""
    resource_table = await get_table_info(conn, "points_resource")
    tables = [t for t in [resource_table] if t is not None]

    return DocsResponse(
        name="points",
        type="resource",
        description="Scoring point values for rubric standards.",
        tables=tables,
        operations=[
            get_operation_info(
                create_point,
                description="Creates a new points resource.",
            ),
            get_operation_info(
                get_points,
                description="Batch retrieves points by IDs.",
            ),
            get_operation_info(
                search_points,
                description="Filtered paginated search returning matching points.",
            ),
        ],
    )
