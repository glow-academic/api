"""Logouts entry documentation."""

import asyncpg  # type: ignore

from app.infra.docs.get_mv_info import get_mv_info
from app.infra.docs.get_operation_info import get_operation_info
from app.infra.docs.get_table_info import get_table_info
from app.infra.docs.types import DocsResponse
from app.tools.entries.logouts.create import create_logout
from app.tools.entries.logouts.get import get_logouts
from app.tools.entries.logouts.refresh import refresh_logouts
from app.tools.entries.logouts.search import search_logouts


async def get_logouts_docs(conn: asyncpg.Connection) -> DocsResponse:
    """Get full documentation for the logouts entry."""
    mv_info = await get_mv_info(conn, "logouts_mv")
    entry_table = await get_table_info(conn, "logouts_entry")
    connection_table = await get_table_info(conn, "profiles_logouts_connection")

    tables = [t for t in [entry_table, connection_table] if t is not None]

    return DocsResponse(
        name="logouts",
        type="entry",
        description=(
            "Logout entries track explicit end-of-session auth events. "
            "Each entry records a logout linked to a session and profile. "
            "The session resolver reads logouts_mv to force a fresh session "
            "on the next request even when the idle gap hasn't elapsed. "
            "Reads are served from the logouts_mv materialized view."
        ),
        materialized_view=mv_info,
        tables=tables,
        operations=[
            get_operation_info(
                create_logout,
                description="Creates a new logout entry and optionally links to a profile.",
            ),
            get_operation_info(
                refresh_logouts,
                description="Refreshes logouts_mv concurrently to reflect latest writes.",
            ),
            get_operation_info(
                get_logouts,
                description="Batch retrieves logout entries by IDs from logouts_mv.",
            ),
            get_operation_info(
                search_logouts,
                description="Filtered paginated search against logouts_mv.",
            ),
        ],
    )
