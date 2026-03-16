"""Sessions entry documentation."""

import asyncpg  # type: ignore

from app.infra.docs.get_mv_info import get_mv_info
from app.infra.docs.get_operation_info import get_operation_info
from app.infra.docs.get_table_info import get_table_info
from app.infra.docs.types import DocsResponse
from app.tools.entries.sessions.create import create_session
from app.tools.entries.sessions.get import get_sessions
from app.tools.entries.sessions.refresh import refresh_sessions
from app.tools.entries.sessions.search import search_sessions


async def get_sessions_docs(conn: asyncpg.Connection) -> DocsResponse:
    """Get full documentation for the sessions entry."""
    mv_info = await get_mv_info(conn, "sessions_mv")
    entry_table = await get_table_info(conn, "sessions_entry")
    connection_table = await get_table_info(conn, "profiles_sessions_connection")

    tables = [t for t in [entry_table, connection_table] if t is not None]

    return DocsResponse(
        name="sessions",
        type="entry",
        description=(
            "User sessions tracking active simulation connections. "
            "Each session links a profile to an active session via a connection table. "
            "Reads are served from the sessions_mv materialized view."
        ),
        materialized_view=mv_info,
        tables=tables,
        operations=[
            get_operation_info(
                create_session,
                description=(
                    "Creates a new session, writing to sessions_entry "
                    "and profiles_sessions_connection."
                ),
            ),
            get_operation_info(
                refresh_sessions,
                description="Refreshes sessions_mv concurrently to reflect latest writes.",
            ),
            get_operation_info(
                get_sessions,
                description="Batch retrieves sessions by IDs from sessions_mv.",
            ),
            get_operation_info(
                search_sessions,
                description="Filtered paginated search against sessions_mv.",
            ),
        ],
    )
