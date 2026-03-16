"""Pricing resource documentation."""

import asyncpg

from app.infra.docs.get_operation_info import get_operation_info
from app.infra.docs.get_table_info import get_table_info
from app.infra.docs.types import DocsResponse
from app.tools.resources.pricing.create import create_pricing
from app.tools.resources.pricing.get import get_pricing
from app.tools.resources.pricing.search import search_pricing


async def get_pricing_docs(conn: asyncpg.Connection) -> DocsResponse:
    """Get full documentation for the pricing resource."""
    resource_table = await get_table_info(conn, "pricing_resource")
    tables = [t for t in [resource_table] if t is not None]

    return DocsResponse(
        name="pricing",
        type="resource",
        description="Pricing tier configurations for model usage.",
        tables=tables,
        operations=[
            get_operation_info(
                create_pricing,
                description="Creates a new pricing resource.",
            ),
            get_operation_info(
                get_pricing,
                description="Batch retrieves pricing by IDs.",
            ),
            get_operation_info(
                search_pricing,
                description="Filtered paginated search returning matching pricing.",
            ),
        ],
    )
