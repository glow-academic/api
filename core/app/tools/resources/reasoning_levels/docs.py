"""Reasoning Levels resource documentation."""

import asyncpg

from app.infra.docs.get_operation_info import get_operation_info
from app.infra.docs.get_table_info import get_table_info
from app.infra.docs.types import DocsResponse
from app.tools.resources.reasoning_levels.create import create_reasoning_level
from app.tools.resources.reasoning_levels.get import get_reasoning_levels
from app.tools.resources.reasoning_levels.search import (
    search_reasoning_levels,
)


async def get_reasoning_levels_docs(conn: asyncpg.Connection) -> DocsResponse:
    """Get full documentation for the reasoning levels resource."""
    resource_table = await get_table_info(conn, "reasoning_levels_resource")
    tables = [t for t in [resource_table] if t is not None]

    return DocsResponse(
        name="reasoning_levels",
        type="resource",
        description="Reasoning depth levels for model configurations.",
        tables=tables,
        operations=[
            get_operation_info(
                create_reasoning_level,
                description="Creates a new reasoning levels resource.",
            ),
            get_operation_info(
                get_reasoning_levels,
                description="Batch retrieves reasoning levels by IDs.",
            ),
            get_operation_info(
                search_reasoning_levels,
                description="Filtered paginated search returning matching reasoning levels.",
            ),
        ],
    )
