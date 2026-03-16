"""Model Positions resource documentation."""

import asyncpg

from app.infra.docs.get_operation_info import get_operation_info
from app.infra.docs.get_table_info import get_table_info
from app.infra.docs.types import DocsResponse
from app.tools.resources.model_positions.create import create_model_position
from app.tools.resources.model_positions.get import get_model_positions
from app.tools.resources.model_positions.search import search_model_positions


async def get_model_positions_docs(conn: asyncpg.Connection) -> DocsResponse:
    """Get full documentation for the model positions resource."""
    resource_table = await get_table_info(conn, "model_positions_resource")
    tables = [t for t in [resource_table] if t is not None]

    return DocsResponse(
        name="model_positions",
        type="resource",
        description="Model position orderings within evals.",
        tables=tables,
        operations=[
            get_operation_info(
                create_model_position,
                description="Creates a new model positions resource.",
            ),
            get_operation_info(
                get_model_positions,
                description="Batch retrieves model positions by IDs.",
            ),
            get_operation_info(
                search_model_positions,
                description="Filtered paginated search returning matching model positions.",
            ),
        ],
    )
