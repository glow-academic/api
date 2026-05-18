"""Model Flags resource documentation."""

import asyncpg

from app.infra.docs.get_operation_info import get_operation_info
from app.infra.docs.get_table_info import get_table_info
from app.infra.docs.types import DocsResponse
from app.tools.resources.model_flags.create import create_model_flag
from app.tools.resources.model_flags.get import get_model_flags
from app.tools.resources.model_flags.search import search_model_flags


async def get_model_flags_docs(conn: asyncpg.Connection) -> DocsResponse:
    """Get full documentation for the model flags resource."""
    resource_table = await get_table_info(conn, "model_flags_resource")
    tables = [t for t in [resource_table] if t is not None]

    return DocsResponse(
        name="model_flags",
        type="resource",
        description="Model-specific flags for eval configurations.",
        tables=tables,
        operations=[
            get_operation_info(
                create_model_flag,
                description="Creates a new model flags resource.",
            ),
            get_operation_info(
                get_model_flags,
                description="Batch retrieves model flags by IDs.",
            ),
            get_operation_info(
                search_model_flags,
                description="Filtered paginated search returning matching model flags.",
            ),
        ],
    )
