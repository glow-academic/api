"""Agent artifact documentation."""

import asyncpg

from app.infra.docs.get_operation_info import get_operation_info
from app.infra.docs.get_table_info import get_table_info
from app.infra.docs.types import DocsResponse
from app.tools.artifacts.agent.create import create_agent
from app.tools.artifacts.agent.delete import delete_agents
from app.tools.artifacts.agent.get import get_agents
from app.tools.artifacts.agent.search import search_agents
from app.tools.artifacts.agent.update import update_agent


async def get_agent_docs(conn: asyncpg.Connection) -> DocsResponse:
    """Get full documentation for the agent artifact."""
    artifact_table = await get_table_info(conn, "agent_artifact")
    tables = [t for t in [artifact_table] if t is not None]

    return DocsResponse(
        name="agent",
        type="artifact",
        description=(
            "Agents define AI assistant profiles for conversations. "
            "Each agent links to resources (names, descriptions, departments, models, "
            "reasoning_levels, temperature_levels, tools, voices) "
            "via junction tables."
        ),
        tables=tables,
        operations=[
            get_operation_info(
                create_agent,
                description="Creates a new agent artifact with optional resource links.",
            ),
            get_operation_info(
                update_agent,
                description="Updates an existing agent's resource links.",
            ),
            get_operation_info(
                get_agents,
                description="Batch retrieves agents by IDs with optional junction data.",
            ),
            get_operation_info(
                search_agents,
                description="Filtered paginated search returning matching agent IDs.",
            ),
            get_operation_info(
                delete_agents,
                description="Deletes agents by IDs. Supports soft delete (active=false) or hard delete (cascade).",
            ),
        ],
    )
