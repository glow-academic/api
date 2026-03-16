"""Examples resource documentation."""

import asyncpg

from app.infra.docs.get_operation_info import get_operation_info
from app.infra.docs.get_table_info import get_table_info
from app.infra.docs.types import DocsResponse
from app.tools.resources.examples.create import create_example
from app.tools.resources.examples.get import get_examples
from app.tools.resources.examples.search import search_examples


async def get_examples_docs(conn: asyncpg.Connection) -> DocsResponse:
    """Get full documentation for the examples resource."""
    resource_table = await get_table_info(conn, "examples_resource")
    tables = [t for t in [resource_table] if t is not None]

    return DocsResponse(
        name="examples",
        type="resource",
        description="Example conversation turns for persona training.",
        tables=tables,
        operations=[
            get_operation_info(
                create_example,
                description="Creates a new examples resource.",
            ),
            get_operation_info(
                get_examples,
                description="Batch retrieves examples by IDs.",
            ),
            get_operation_info(
                search_examples,
                description="Filtered paginated search returning matching examples.",
            ),
        ],
    )
