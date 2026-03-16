"""Attempt highlight entry documentation."""

import asyncpg  # type: ignore

from app.infra.docs.get_mv_info import get_mv_info
from app.infra.docs.get_operation_info import get_operation_info
from app.infra.docs.get_table_info import get_table_info
from app.infra.docs.types import DocsResponse
from app.tools.entries.attempt_highlight.create import (
    create_attempt_highlight,
)
from app.tools.entries.attempt_highlight.get import get_attempt_highlights
from app.tools.entries.attempt_highlight.refresh import (
    refresh_attempt_highlight,
)
from app.tools.entries.attempt_highlight.search import (
    search_attempt_highlights,
)


async def get_attempt_highlight_docs(conn: asyncpg.Connection) -> DocsResponse:
    """Get full documentation for the attempt_highlight entry."""
    mv_info = await get_mv_info(conn, "attempt_highlight_mv")
    entry_table = await get_table_info(conn, "attempt_highlight_entry")

    tables = [t for t in [entry_table] if t is not None]

    return DocsResponse(
        name="attempt_highlight",
        type="entry",
        description=(
            "Highlight records within strengths, identifying notable sections of text. "
            "Each highlight references a strength entry, includes a section identifier, "
            "and maintains an index for ordering. "
            "Reads are served from the attempt_highlight_mv materialized view."
        ),
        materialized_view=mv_info,
        tables=tables,
        operations=[
            get_operation_info(
                create_attempt_highlight,
                description="Creates a new attempt_highlight entry within a strength.",
            ),
            get_operation_info(
                refresh_attempt_highlight,
                description="Refreshes attempt_highlight_mv concurrently.",
            ),
            get_operation_info(
                get_attempt_highlights,
                description="Batch retrieves highlights by IDs from attempt_highlight_mv.",
            ),
            get_operation_info(
                search_attempt_highlights,
                description="Filtered paginated search against attempt_highlight_mv.",
            ),
        ],
    )
