"""Prompts resource documentation."""

import asyncpg

from app.infra.docs.get_operation_info import get_operation_info
from app.infra.docs.get_table_info import get_table_info
from app.infra.docs.types import DocsResponse
from app.tools.resources.prompts.create import create_prompt
from app.tools.resources.prompts.get import get_prompts
from app.tools.resources.prompts.search import search_prompts


async def get_prompts_docs(conn: asyncpg.Connection) -> DocsResponse:
    """Get full documentation for the prompts resource."""
    resource_table = await get_table_info(conn, "prompts_resource")
    tables = [t for t in [resource_table] if t is not None]

    return DocsResponse(
        name="prompts",
        type="resource",
        description="Prompt text templates for agent configurations.",
        tables=tables,
        operations=[
            get_operation_info(
                create_prompt,
                description="Creates a new prompts resource.",
            ),
            get_operation_info(
                get_prompts,
                description="Batch retrieves prompts by IDs.",
            ),
            get_operation_info(
                search_prompts,
                description="Filtered paginated search returning matching prompts.",
            ),
        ],
    )
