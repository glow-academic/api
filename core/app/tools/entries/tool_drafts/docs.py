"""Tool drafts entry documentation."""

import asyncpg  # type: ignore

from app.infra.docs.get_mv_info import get_mv_info
from app.infra.docs.get_operation_info import get_operation_info
from app.infra.docs.get_table_info import get_table_info
from app.infra.docs.types import DocsResponse
from app.tools.entries.tool_drafts.create import create_tool_draft
from app.tools.entries.tool_drafts.get import get_tool_drafts
from app.tools.entries.tool_drafts.refresh import refresh_tool_drafts
from app.tools.entries.tool_drafts.search import search_tool_drafts


async def get_tool_drafts_docs(conn: asyncpg.Connection) -> DocsResponse:
    """Get full documentation for the tool_drafts entry."""
    mv_info = await get_mv_info(conn, "tool_drafts_mv")
    entry_table = await get_table_info(conn, "tool_drafts_entry")
    arg_positions_connection = await get_table_info(
        conn, "tool_drafts_arg_positions_connection"
    )
    args_connection = await get_table_info(conn, "tool_drafts_args_connection")
    args_outputs_connection = await get_table_info(
        conn, "tool_drafts_args_outputs_connection"
    )
    departments_connection = await get_table_info(
        conn, "tool_drafts_departments_connection"
    )
    descriptions_connection = await get_table_info(
        conn, "tool_drafts_descriptions_connection"
    )
    flags_connection = await get_table_info(conn, "tool_drafts_flags_connection")
    names_connection = await get_table_info(conn, "tool_drafts_names_connection")
    profiles_connection = await get_table_info(conn, "tool_drafts_profiles_connection")

    tables = [
        t
        for t in [
            entry_table,
            arg_positions_connection,
            args_connection,
            args_outputs_connection,
            departments_connection,
            descriptions_connection,
            flags_connection,
            names_connection,
            profiles_connection,
        ]
        if t is not None
    ]

    return DocsResponse(
        name="tool_drafts",
        type="entry",
        description=(
            "Tool draft artifacts with support for multiple resource connections. "
            "Each draft links to arg positions, args, args outputs, departments, descriptions, "
            "flags, names, and profiles via connection tables. "
            "Reads are served from the tool_drafts_mv materialized view."
        ),
        materialized_view=mv_info,
        tables=tables,
        operations=[
            get_operation_info(
                create_tool_draft,
                description=(
                    "Creates a new tool draft, writing to tool_drafts_entry "
                    "and all relevant connection tables."
                ),
            ),
            get_operation_info(
                refresh_tool_drafts,
                description="Refreshes tool_drafts_mv concurrently to reflect latest writes.",
            ),
            get_operation_info(
                get_tool_drafts,
                description="Batch retrieves tool drafts by IDs from tool_drafts_mv.",
            ),
            get_operation_info(
                search_tool_drafts,
                description="Filtered paginated search against tool_drafts_mv.",
            ),
        ],
    )
