"""Activity entry documentation."""

import asyncpg  # type: ignore

from app.infra.docs.get_mv_info import get_mv_info
from app.infra.docs.get_operation_info import get_operation_info
from app.infra.docs.get_table_info import get_table_info
from app.infra.docs.types import DocsResponse
from app.tools.entries.activity.create import create_activity
from app.tools.entries.activity.get import get_activity
from app.tools.entries.activity.refresh import refresh_activity
from app.tools.entries.activity.search import search_activity


async def get_activity_docs(conn: asyncpg.Connection) -> DocsResponse:
    """Get full documentation for the activity entry."""
    mv_info = await get_mv_info(conn, "activity_mv")
    entry_table = await get_table_info(conn, "activity_entry")
    connection_table = await get_table_info(conn, "profiles_activity_connection")

    tables = [t for t in [entry_table, connection_table] if t is not None]

    return DocsResponse(
        name="activity",
        type="entry",
        description=(
            "Activity entries track user presence heartbeats. "
            "Each entry records a connect/disconnect event linked to a session and profile. "
            "Reads are served from the activity_mv materialized view."
        ),
        materialized_view=mv_info,
        tables=tables,
        operations=[
            get_operation_info(
                create_activity,
                description="Creates a new activity entry and optionally links to a profile.",
            ),
            get_operation_info(
                refresh_activity,
                description="Refreshes activity_mv concurrently to reflect latest writes.",
            ),
            get_operation_info(
                get_activity,
                description="Batch retrieves activity entries by IDs from activity_mv.",
            ),
            get_operation_info(
                search_activity,
                description="Filtered paginated search against activity_mv.",
            ),
        ],
    )
