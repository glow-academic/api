"""Attempt entry documentation."""

import asyncpg  # type: ignore

from app.infra.docs.get_mv_info import get_mv_info
from app.infra.docs.get_operation_info import get_operation_info
from app.infra.docs.get_table_info import get_table_info
from app.infra.docs.types import DocsResponse
from app.tools.entries.attempt.create import create_attempt
from app.tools.entries.attempt.get import get_attempts
from app.tools.entries.attempt.refresh import refresh_attempt
from app.tools.entries.attempt.search import search_attempts


async def get_attempt_docs(conn: asyncpg.Connection) -> DocsResponse:
    """Get full documentation for the attempt entry."""
    mv_info = await get_mv_info(conn, "attempt_mv")
    entry_table = await get_table_info(conn, "attempt_entry")
    connection_table = await get_table_info(conn, "attempt_profiles_connection")

    tables = [t for t in [entry_table, connection_table] if t is not None]

    return DocsResponse(
        name="attempt",
        type="entry",
        description=(
            "Main attempt records tracking individual simulation attempts. "
            "Each attempt links to a profile via a connection table and contains metadata "
            "about infinite mode, number of chats, and practice/MCP flags. "
            "Reads are served from the attempt_mv materialized view."
        ),
        materialized_view=mv_info,
        tables=tables,
        operations=[
            get_operation_info(
                create_attempt,
                description=(
                    "Creates a new attempt entry with basic metadata and "
                    "inserts an attempt_profiles_connection row."
                ),
            ),
            get_operation_info(
                refresh_attempt,
                description="Refreshes attempt_mv concurrently to reflect latest writes.",
            ),
            get_operation_info(
                get_attempts,
                description="Batch retrieves attempts by IDs from attempt_mv.",
            ),
            get_operation_info(
                search_attempts,
                description="Filtered paginated search against attempt_mv.",
            ),
        ],
    )
