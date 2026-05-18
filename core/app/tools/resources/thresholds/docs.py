"""Thresholds resource documentation."""

import asyncpg

from app.infra.docs.get_operation_info import get_operation_info
from app.infra.docs.get_table_info import get_table_info
from app.infra.docs.types import DocsResponse
from app.tools.resources.thresholds.create import create_threshold
from app.tools.resources.thresholds.get import get_thresholds
from app.tools.resources.thresholds.search import search_thresholds


async def get_thresholds_docs(conn: asyncpg.Connection) -> DocsResponse:
    """Get full documentation for the thresholds resource."""
    resource_table = await get_table_info(conn, "thresholds_resource")
    tables = [t for t in [resource_table] if t is not None]

    return DocsResponse(
        name="thresholds",
        type="resource",
        description="Threshold values for setting configurations.",
        tables=tables,
        operations=[
            get_operation_info(
                create_threshold,
                description="Creates a new thresholds resource.",
            ),
            get_operation_info(
                get_thresholds,
                description="Batch retrieves thresholds by IDs.",
            ),
            get_operation_info(
                search_thresholds,
                description="Filtered paginated search returning matching thresholds.",
            ),
        ],
    )
