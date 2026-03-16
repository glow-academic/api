"""Instructions resource documentation."""

import asyncpg

from app.infra.docs.get_operation_info import get_operation_info
from app.infra.docs.get_table_info import get_table_info
from app.infra.docs.types import DocsResponse
from app.tools.resources.instructions.create import create_instruction
from app.tools.resources.instructions.get import get_instructions
from app.tools.resources.instructions.search import search_instructions


async def get_instructions_docs(conn: asyncpg.Connection) -> DocsResponse:
    """Get full documentation for the instructions resource."""
    resource_table = await get_table_info(conn, "instructions_resource")
    tables = [t for t in [resource_table] if t is not None]

    return DocsResponse(
        name="instructions",
        type="resource",
        description="System instruction text blocks for agents and personas.",
        tables=tables,
        operations=[
            get_operation_info(
                create_instruction,
                description="Creates a new instructions resource.",
            ),
            get_operation_info(
                get_instructions,
                description="Batch retrieves instructions by IDs.",
            ),
            get_operation_info(
                search_instructions,
                description="Filtered paginated search returning matching instructions.",
            ),
        ],
    )
