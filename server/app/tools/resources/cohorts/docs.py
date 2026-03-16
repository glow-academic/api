"""Cohorts resource documentation."""

import asyncpg

from app.infra.docs.get_operation_info import get_operation_info
from app.infra.docs.get_table_info import get_table_info
from app.infra.docs.types import DocsResponse
from app.tools.resources.cohorts.create import create_cohort
from app.tools.resources.cohorts.get import get_cohorts
from app.tools.resources.cohorts.search import search_cohorts


async def get_cohorts_docs(conn: asyncpg.Connection) -> DocsResponse:
    """Get full documentation for the cohorts resource."""
    resource_table = await get_table_info(conn, "cohorts_resource")
    tables = [t for t in [resource_table] if t is not None]

    return DocsResponse(
        name="cohorts",
        type="resource",
        description="Cohort reference IDs linking to cohort artifacts.",
        tables=tables,
        operations=[
            get_operation_info(
                create_cohort,
                description="Creates a new cohorts resource.",
            ),
            get_operation_info(
                get_cohorts,
                description="Batch retrieves cohorts by IDs.",
            ),
            get_operation_info(
                search_cohorts,
                description="Filtered paginated search returning matching cohorts.",
            ),
        ],
    )
