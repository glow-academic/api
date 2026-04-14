"""Refresh entry documentation."""

import asyncpg  # type: ignore

from app.infra.docs.get_operation_info import get_operation_info
from app.infra.docs.get_table_info import get_table_info
from app.infra.docs.types import DocsResponse
from app.tools.entries.refreshes.create import create_refresh
from app.tools.entries.refreshes.get import get_refreshes
from app.tools.entries.refreshes.search import search_refreshes


async def get_refreshes_docs(conn: asyncpg.Connection) -> DocsResponse:
    """Get full documentation for the refresh entry."""
    entry_table = await get_table_info(conn, "refresh_entry")

    tables = [t for t in [entry_table] if t is not None]

    return DocsResponse(
        name="refreshes",
        type="entry",
        description=(
            "Refresh entries track MV refresh operations. Each entry records "
            "a single target (materialized view) that was refreshed, grouped "
            "by operation_key. Enables per-target throttling and provides a "
            "system of record for all refresh activity."
        ),
        materialized_view=None,
        tables=tables,
        operations=[
            get_operation_info(
                create_refresh,
                description="Creates a new refresh entry for an MV target.",
            ),
            get_operation_info(
                get_refreshes,
                description="Retrieves refresh entries by IDs from refresh_mv.",
            ),
            get_operation_info(
                search_refreshes,
                description="Filtered paginated search against refresh_mv.",
            ),
        ],
    )
