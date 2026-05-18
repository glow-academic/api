"""Attempt strength entry documentation."""

import asyncpg  # type: ignore

from app.infra.docs.get_mv_info import get_mv_info
from app.infra.docs.get_operation_info import get_operation_info
from app.infra.docs.get_table_info import get_table_info
from app.infra.docs.types import DocsResponse
from app.tools.entries.attempt_strength.create import create_attempt_strength
from app.tools.entries.attempt_strength.get import get_attempt_strengths
from app.tools.entries.attempt_strength.refresh import (
    refresh_attempt_strength,
)
from app.tools.entries.attempt_strength.search import search_attempt_strengths


async def get_attempt_strength_docs(conn: asyncpg.Connection) -> DocsResponse:
    """Get full documentation for the attempt_strength entry."""
    mv_info = await get_mv_info(conn, "attempt_strength_mv")
    entry_table = await get_table_info(conn, "attempt_strength_entry")

    tables = [t for t in [entry_table] if t is not None]

    return DocsResponse(
        name="attempt_strength",
        type="entry",
        description=(
            "Strength observations linked to grades and messages, highlighting positive aspects. "
            "Each strength contains a name and description, and may have associated "
            "highlight entries that identify notable sections. "
            "Reads are served from the attempt_strength_mv materialized view."
        ),
        materialized_view=mv_info,
        tables=tables,
        operations=[
            get_operation_info(
                create_attempt_strength,
                description="Creates a new attempt_strength entry for a grade and message.",
            ),
            get_operation_info(
                refresh_attempt_strength,
                description="Refreshes attempt_strength_mv concurrently.",
            ),
            get_operation_info(
                get_attempt_strengths,
                description="Batch retrieves strengths by IDs from attempt_strength_mv.",
            ),
            get_operation_info(
                search_attempt_strengths,
                description="Filtered paginated search against attempt_strength_mv.",
            ),
        ],
    )
