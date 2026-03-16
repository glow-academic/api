"""Problems entry documentation."""

import asyncpg  # type: ignore

from app.infra.docs.get_mv_info import get_mv_info
from app.infra.docs.get_operation_info import get_operation_info
from app.infra.docs.get_table_info import get_table_info
from app.infra.docs.types import DocsResponse
from app.tools.entries.problems.create import create_problem
from app.tools.entries.problems.get import get_problems
from app.tools.entries.problems.refresh import refresh_problems
from app.tools.entries.problems.search import search_problems


async def get_problems_docs(conn: asyncpg.Connection) -> DocsResponse:
    """Get full documentation for the problems entry."""
    mv_info = await get_mv_info(conn, "problems_mv")
    entry_table = await get_table_info(conn, "problems_entry")
    connection_table = await get_table_info(conn, "profiles_problems_connection")

    tables = [t for t in [entry_table, connection_table] if t is not None]

    return DocsResponse(
        name="problems",
        type="entry",
        description=(
            "Problem entries capture user-submitted feedback events such as bugs, "
            "feature requests, and questions. Each entry belongs to a session and "
            "optionally links to a profile. Resolution state is tracked via a lateral "
            "join to resolves_entry. Reads are served from the problems_mv materialized view."
        ),
        materialized_view=mv_info,
        tables=tables,
        operations=[
            get_operation_info(
                create_problem,
                description="Creates a new problem entry and optionally links to a profile.",
            ),
            get_operation_info(
                refresh_problems,
                description="Refreshes problems_mv concurrently to reflect latest writes.",
            ),
            get_operation_info(
                get_problems,
                description="Batch retrieves problem entries by IDs from problems_mv.",
            ),
            get_operation_info(
                search_problems,
                description="Filtered paginated search against problems_mv.",
            ),
        ],
    )
