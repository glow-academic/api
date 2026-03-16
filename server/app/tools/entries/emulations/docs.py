"""Emulations entry documentation."""

import asyncpg  # type: ignore

from app.infra.docs.get_mv_info import get_mv_info
from app.infra.docs.get_operation_info import get_operation_info
from app.infra.docs.get_table_info import get_table_info
from app.infra.docs.types import DocsResponse
from app.tools.entries.emulations.create import create_emulation
from app.tools.entries.emulations.get import get_emulations
from app.tools.entries.emulations.refresh import refresh_emulations
from app.tools.entries.emulations.search import search_emulations


async def get_emulations_docs(conn: asyncpg.Connection) -> DocsResponse:
    """Get full documentation for the emulations entry."""
    mv_info = await get_mv_info(conn, "emulations_mv")
    entry_table = await get_table_info(conn, "emulations_entry")
    connection_table = await get_table_info(conn, "profiles_emulations_connection")

    tables = [t for t in [entry_table, connection_table] if t is not None]

    return DocsResponse(
        name="emulations",
        type="entry",
        description=(
            "Emulation entries track grant-based session emulations. "
            "Each entry links a grant to a session and optionally a profile. "
            "Reads are served from the emulations_mv materialized view."
        ),
        materialized_view=mv_info,
        tables=tables,
        operations=[
            get_operation_info(
                create_emulation,
                description="Creates a new emulation entry and optionally links to a profile.",
            ),
            get_operation_info(
                refresh_emulations,
                description="Refreshes emulations_mv concurrently to reflect latest writes.",
            ),
            get_operation_info(
                get_emulations,
                description="Batch retrieves emulation entries by IDs from emulations_mv.",
            ),
            get_operation_info(
                search_emulations,
                description="Filtered paginated search against emulations_mv.",
            ),
        ],
    )
