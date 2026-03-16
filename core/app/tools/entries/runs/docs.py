"""Runs entry documentation."""

import asyncpg  # type: ignore

from app.infra.docs.get_mv_info import get_mv_info
from app.infra.docs.get_operation_info import get_operation_info
from app.infra.docs.get_table_info import get_table_info
from app.infra.docs.types import DocsResponse
from app.tools.entries.runs.create import create_run
from app.tools.entries.runs.get import get_run
from app.tools.entries.runs.refresh import refresh_runs_internal
from app.tools.entries.runs.search import search_runs


async def get_runs_docs(conn: asyncpg.Connection) -> DocsResponse:
    """Get full documentation for the runs entry."""
    mv_info = await get_mv_info(conn, "runs_mv")
    entry_table = await get_table_info(conn, "runs_entry")
    connection_tables = [
        await get_table_info(conn, "profiles_runs_connection"),
        await get_table_info(conn, "runs_agents_connection"),
    ]

    tables = [t for t in [entry_table] + connection_tables if t is not None]

    return DocsResponse(
        name="runs",
        type="entry",
        description=(
            "Runs entries track execution runs within groups and sessions. "
            "Each run links to a group and optionally to profiles and agents via connection tables. "
            "Reads are served from the runs_mv materialized view."
        ),
        materialized_view=mv_info,
        tables=tables,
        operations=[
            get_operation_info(
                create_run,
                description=(
                    "Creates a new runs entry with optional profile and agent links."
                ),
            ),
            get_operation_info(
                refresh_runs_internal,
                description="Refreshes runs_mv concurrently to reflect latest writes.",
            ),
            get_operation_info(
                get_run,
                description="Batch retrieves runs entries by IDs from runs_mv.",
            ),
            get_operation_info(
                search_runs,
                description="Filtered paginated search against runs_mv.",
            ),
        ],
    )
