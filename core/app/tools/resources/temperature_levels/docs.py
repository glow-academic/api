"""Temperature Levels resource documentation."""

import asyncpg

from app.infra.docs.get_operation_info import get_operation_info
from app.infra.docs.get_table_info import get_table_info
from app.infra.docs.types import DocsResponse
from app.tools.resources.temperature_levels.create import (
    create_temperature_level,
)
from app.tools.resources.temperature_levels.get import get_temperature_levels
from app.tools.resources.temperature_levels.search import (
    search_temperature_levels,
)


async def get_temperature_levels_docs(conn: asyncpg.Connection) -> DocsResponse:
    """Get full documentation for the temperature levels resource."""
    resource_table = await get_table_info(conn, "temperature_levels_resource")
    tables = [t for t in [resource_table] if t is not None]

    return DocsResponse(
        name="temperature_levels",
        type="resource",
        description="Temperature sampling levels for model configurations.",
        tables=tables,
        operations=[
            get_operation_info(
                create_temperature_level,
                description="Creates a new temperature levels resource.",
            ),
            get_operation_info(
                get_temperature_levels,
                description="Batch retrieves temperature levels by IDs.",
            ),
            get_operation_info(
                search_temperature_levels,
                description="Filtered paginated search returning matching temperature levels.",
            ),
        ],
    )
