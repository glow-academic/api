"""Calls entry documentation."""

import asyncpg  # type: ignore

from app.infra.docs.get_operation_info import get_operation_info
from app.infra.docs.get_table_info import get_table_info
from app.infra.docs.types import DocsResponse
from app.tools.entries.calls.create import create_call
from app.tools.entries.calls.get import get_call
from app.tools.entries.calls.search import search_calls


async def get_calls_docs(conn: asyncpg.Connection) -> DocsResponse:
    """Get full documentation for the calls entry."""
    entry_table = await get_table_info(conn, "calls_entry")
    tools_connection = await get_table_info(conn, "tools_calls_connection")

    tables = [t for t in [entry_table, tools_connection] if t is not None]

    return DocsResponse(
        name="calls",
        type="entry",
        description=(
            "Call entries track individual function calls made during execution. "
            "Each call is linked to a run and session, and can optionally reference a tool resource. "
            "Reads are served directly from the calls_entry table."
        ),
        materialized_view=None,
        tables=tables,
        operations=[
            get_operation_info(
                create_call,
                description=(
                    "Creates a new call entry and optionally links it to a tool resource "
                    "via tools_calls_connection."
                ),
            ),
            get_operation_info(
                get_call,
                description="Retrieves a single call entry by ID from calls_entry.",
            ),
            get_operation_info(
                search_calls,
                description="Filtered paginated search against calls_mv.",
            ),
        ],
    )
