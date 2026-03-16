"""Attempt home bridge entry documentation."""

import asyncpg  # type: ignore

from app.infra.docs.get_mv_info import get_mv_info
from app.infra.docs.get_operation_info import get_operation_info
from app.infra.docs.get_table_info import get_table_info
from app.infra.docs.types import DocsResponse
from app.tools.entries.attempt_home.create import create_attempt_home
from app.tools.entries.attempt_home.get import get_attempt_home
from app.tools.entries.attempt_home.refresh import refresh_attempt_home
from app.tools.entries.attempt_home.search import (
    search_attempt_homes,
)


async def get_attempt_home_docs(conn: asyncpg.Connection) -> DocsResponse:
    """Get full documentation for the attempt_home entry."""
    mv_info = await get_mv_info(conn, "attempt_home_mv")
    entry_table = await get_table_info(conn, "attempt_home_entry")

    tables = [t for t in [entry_table] if t is not None]

    return DocsResponse(
        name="attempt_home",
        type="entry",
        description=(
            "Attempt home bridge entries link attempts to home page artifacts via a session. "
            "This bridge table connects the attempt and home domains. "
            "Reads are served from the attempt_home_mv materialized view."
        ),
        materialized_view=mv_info,
        tables=tables,
        operations=[
            get_operation_info(
                create_attempt_home,
                description=(
                    "Creates a new attempt_home entry linking an attempt "
                    "to a home artifact within a session."
                ),
            ),
            get_operation_info(
                get_attempt_home,
                description="Retrieves attempt_home entries by attempt IDs from MV.",
            ),
            get_operation_info(
                refresh_attempt_home,
                description="Refreshes attempt_home_mv concurrently to reflect latest writes.",
            ),
            get_operation_info(
                search_attempt_homes,
                description="Filtered paginated search against attempt_home_mv.",
            ),
        ],
    )
