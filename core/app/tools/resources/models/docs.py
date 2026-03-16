"""Models resource documentation."""

import asyncpg

from app.infra.docs.get_operation_info import get_operation_info
from app.infra.docs.get_table_info import get_table_info
from app.infra.docs.types import DocsResponse
from app.tools.resources.models.create import create_model
from app.tools.resources.models.get import get_models
from app.tools.resources.models.search import search_models


async def get_models_docs(conn: asyncpg.Connection) -> DocsResponse:
    """Get full documentation for the models resource."""
    resource_table = await get_table_info(conn, "models_resource")
    tables = [t for t in [resource_table] if t is not None]

    return DocsResponse(
        name="models",
        type="resource",
        description="Model reference IDs linking to model artifacts.",
        tables=tables,
        operations=[
            get_operation_info(
                create_model,
                description="Creates a new models resource.",
            ),
            get_operation_info(
                get_models,
                description="Batch retrieves models by IDs.",
            ),
            get_operation_info(
                search_models,
                description="Filtered paginated search returning matching models.",
            ),
        ],
    )
