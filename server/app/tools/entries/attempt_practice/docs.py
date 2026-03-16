"""Attempt practice bridge entry documentation."""

import asyncpg  # type: ignore

from app.infra.docs.get_mv_info import get_mv_info
from app.infra.docs.get_operation_info import get_operation_info
from app.infra.docs.get_table_info import get_table_info
from app.infra.docs.types import DocsResponse
from app.tools.entries.attempt_practice.create import (
    create_attempt_practice,
)
from app.tools.entries.attempt_practice.get import (
    get_attempt_practice,
)
from app.tools.entries.attempt_practice.refresh import (
    refresh_attempt_practice,
)
from app.tools.entries.attempt_practice.search import (
    search_attempt_practice_entries,
)


async def get_attempt_practice_docs(conn: asyncpg.Connection) -> DocsResponse:
    """Get full documentation for the attempt_practice entry."""
    mv_info = await get_mv_info(conn, "attempt_practice_mv")
    entry_table = await get_table_info(conn, "attempt_practice_entry")

    tables = [t for t in [entry_table] if t is not None]

    return DocsResponse(
        name="attempt_practice",
        type="entry",
        description=(
            "Attempt practice bridge entries link attempts to practice artifacts via a session. "
            "This bridge table connects the attempt and practice domains. "
            "Reads are served from the attempt_practice_mv materialized view."
        ),
        materialized_view=mv_info,
        tables=tables,
        operations=[
            get_operation_info(
                create_attempt_practice,
                description=(
                    "Creates a new attempt_practice entry linking an attempt "
                    "to a practice artifact within a session."
                ),
            ),
            get_operation_info(
                get_attempt_practice,
                description="Retrieves attempt_practice entries by attempt IDs from MV.",
            ),
            get_operation_info(
                refresh_attempt_practice,
                description="Refreshes attempt_practice_mv concurrently to reflect latest writes.",
            ),
            get_operation_info(
                search_attempt_practice_entries,
                description="Filtered paginated search against attempt_practice_mv.",
            ),
        ],
    )
