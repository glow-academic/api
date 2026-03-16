"""Agents resource documentation."""

import asyncpg

from app.infra.docs.get_operation_info import get_operation_info
from app.infra.docs.get_table_info import get_table_info
from app.infra.docs.types import DocsResponse
from app.tools.resources.agents.create import create_agent
from app.tools.resources.agents.get import get_agents
from app.tools.resources.agents.search import search_agents


async def get_agents_docs(conn: asyncpg.Connection) -> DocsResponse:
    """Get full documentation for the agents resource."""
    resource_table = await get_table_info(conn, "agents_resource")
    tables = [t for t in [resource_table] if t is not None]

    return DocsResponse(
        name="agents",
        type="resource",
        description="Agent reference IDs linking to agent artifacts.",
        tables=tables,
        operations=[
            get_operation_info(
                create_agent,
                description="Creates a new agents resource.",
            ),
            get_operation_info(
                get_agents,
                description="Batch retrieves agents by IDs.",
            ),
            get_operation_info(
                search_agents,
                description="Filtered paginated search returning matching agents.",
            ),
        ],
    )
