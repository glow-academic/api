"""Model Rubrics resource documentation."""

import asyncpg

from app.infra.docs.get_operation_info import get_operation_info
from app.infra.docs.get_table_info import get_table_info
from app.infra.docs.types import DocsResponse
from app.tools.resources.model_rubrics.create import create_model_rubric
from app.tools.resources.model_rubrics.get import get_model_rubrics
from app.tools.resources.model_rubrics.search import search_model_rubrics


async def get_model_rubrics_docs(conn: asyncpg.Connection) -> DocsResponse:
    """Get full documentation for the model rubrics resource."""
    resource_table = await get_table_info(conn, "model_rubrics_resource")
    tables = [t for t in [resource_table] if t is not None]

    return DocsResponse(
        name="model_rubrics",
        type="resource",
        description="Model-rubric associations for eval scoring.",
        tables=tables,
        operations=[
            get_operation_info(
                create_model_rubric,
                description="Creates a new model rubrics resource.",
            ),
            get_operation_info(
                get_model_rubrics,
                description="Batch retrieves model rubrics by IDs.",
            ),
            get_operation_info(
                search_model_rubrics,
                description="Filtered paginated search returning matching model rubrics.",
            ),
        ],
    )
