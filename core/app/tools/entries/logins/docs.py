"""Logins entry documentation."""

import asyncpg  # type: ignore

from app.infra.docs.get_mv_info import get_mv_info
from app.infra.docs.get_operation_info import get_operation_info
from app.infra.docs.get_table_info import get_table_info
from app.infra.docs.types import DocsResponse
from app.tools.entries.logins.create import create_login
from app.tools.entries.logins.get import get_logins
from app.tools.entries.logins.refresh import refresh_logins
from app.tools.entries.logins.search import search_logins


async def get_logins_docs(conn: asyncpg.Connection) -> DocsResponse:
    """Get full documentation for the logins entry."""
    mv_info = await get_mv_info(conn, "logins_mv")
    entry_table = await get_table_info(conn, "logins_entry")
    connection_table = await get_table_info(conn, "profiles_logins_connection")

    tables = [t for t in [entry_table, connection_table] if t is not None]

    return DocsResponse(
        name="logins",
        type="entry",
        description=(
            "Login entries track authentication events. "
            "Each entry records a login linked to a session and profile. "
            "Reads are served from the logins_mv materialized view."
        ),
        materialized_view=mv_info,
        tables=tables,
        operations=[
            get_operation_info(
                create_login,
                description="Creates a new login entry and optionally links to a profile.",
            ),
            get_operation_info(
                refresh_logins,
                description="Refreshes logins_mv concurrently to reflect latest writes.",
            ),
            get_operation_info(
                get_logins,
                description="Batch retrieves login entries by IDs from logins_mv.",
            ),
            get_operation_info(
                search_logins,
                description="Filtered paginated search against logins_mv.",
            ),
        ],
    )
