"""Tool artifact documentation."""

import asyncpg

from app.infra.docs.get_operation_info import get_operation_info
from app.infra.docs.get_table_info import get_table_info
from app.infra.docs.types import DocsResponse
from app.tools.artifacts.tool.create import create_tool
from app.tools.artifacts.tool.delete import delete_tools
from app.tools.artifacts.tool.get import get_tools
from app.tools.artifacts.tool.search import search_tools
from app.tools.artifacts.tool.update import update_tool


async def get_tool_docs(conn: asyncpg.Connection) -> DocsResponse:
    """Get full documentation for the tool artifact."""
    artifact_table = await get_table_info(conn, "tool_artifact")
    tables = [t for t in [artifact_table] if t is not None]

    return DocsResponse(
        name="tool",
        type="artifact",
        description=(
            "Tools define callable functions available to AI agents during conversations. "
            "Each tool links to resources (names, descriptions, departments, args, "
            "arg_positions, args_outputs, artifacts, entries, operations, resources) via "
            "junction tables."
        ),
        tables=tables,
        operations=[
            get_operation_info(
                create_tool,
                description="Creates a new tool artifact with optional resource links.",
            ),
            get_operation_info(
                update_tool, description="Updates an existing tool's resource links."
            ),
            get_operation_info(
                get_tools,
                description="Batch retrieves tools by IDs with optional junction data.",
            ),
            get_operation_info(
                search_tools,
                description="Filtered paginated search returning matching tool IDs.",
            ),
            get_operation_info(
                delete_tools,
                description="Deletes tools by IDs. Supports soft delete (active=false) or hard delete (cascade).",
            ),
        ],
    )
