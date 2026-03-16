"""Attempt improvement entry documentation."""

import asyncpg  # type: ignore

from app.infra.docs.get_mv_info import get_mv_info
from app.infra.docs.get_operation_info import get_operation_info
from app.infra.docs.get_table_info import get_table_info
from app.infra.docs.types import DocsResponse
from app.tools.entries.attempt_improvement.create import (
    create_attempt_improvement,
)
from app.tools.entries.attempt_improvement.get import get_attempt_improvements
from app.tools.entries.attempt_improvement.refresh import (
    refresh_attempt_improvement,
)
from app.tools.entries.attempt_improvement.search import (
    search_attempt_improvements,
)


async def get_attempt_improvement_docs(conn: asyncpg.Connection) -> DocsResponse:
    """Get full documentation for the attempt_improvement entry."""
    mv_info = await get_mv_info(conn, "attempt_improvement_mv")
    entry_table = await get_table_info(conn, "attempt_improvement_entry")

    tables = [t for t in [entry_table] if t is not None]

    return DocsResponse(
        name="attempt_improvement",
        type="entry",
        description=(
            "Improvement suggestions linked to grades and messages. "
            "Each improvement contains a name and description, and may have "
            "associated replacement entries that detail the improvements. "
            "Reads are served from the attempt_improvement_mv materialized view."
        ),
        materialized_view=mv_info,
        tables=tables,
        operations=[
            get_operation_info(
                create_attempt_improvement,
                description="Creates a new attempt_improvement entry for a grade and message.",
            ),
            get_operation_info(
                refresh_attempt_improvement,
                description="Refreshes attempt_improvement_mv concurrently.",
            ),
            get_operation_info(
                get_attempt_improvements,
                description="Batch retrieves improvements by IDs from attempt_improvement_mv.",
            ),
            get_operation_info(
                search_attempt_improvements,
                description="Filtered paginated search against attempt_improvement_mv.",
            ),
        ],
    )
