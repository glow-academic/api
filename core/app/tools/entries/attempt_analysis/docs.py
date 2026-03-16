"""Attempt analysis entry documentation."""

import asyncpg  # type: ignore

from app.infra.docs.get_mv_info import get_mv_info
from app.infra.docs.get_operation_info import get_operation_info
from app.infra.docs.get_table_info import get_table_info
from app.infra.docs.types import DocsResponse
from app.tools.entries.attempt_analysis.create import create_attempt_analysis
from app.tools.entries.attempt_analysis.get import get_attempt_analyses
from app.tools.entries.attempt_analysis.refresh import (
    refresh_attempt_analysis,
)
from app.tools.entries.attempt_analysis.search import search_attempt_analyses


async def get_attempt_analysis_docs(conn: asyncpg.Connection) -> DocsResponse:
    """Get full documentation for the attempt_analysis entry."""
    mv_info = await get_mv_info(conn, "attempt_analysis_mv")
    entry_table = await get_table_info(conn, "attempt_analysis_entry")

    tables = [t for t in [entry_table] if t is not None]

    return DocsResponse(
        name="attempt_analysis",
        type="entry",
        description=(
            "Analysis feedback entries attached to grades. "
            "Each analysis contains content generated from a call and references a grade. "
            "Reads are served from the attempt_analysis_mv materialized view."
        ),
        materialized_view=mv_info,
        tables=tables,
        operations=[
            get_operation_info(
                create_attempt_analysis,
                description="Creates a new attempt_analysis entry linked to a grade.",
            ),
            get_operation_info(
                refresh_attempt_analysis,
                description="Refreshes attempt_analysis_mv concurrently.",
            ),
            get_operation_info(
                get_attempt_analyses,
                description="Batch retrieves analyses by IDs from attempt_analysis_mv.",
            ),
            get_operation_info(
                search_attempt_analyses,
                description="Filtered paginated search against attempt_analysis_mv.",
            ),
        ],
    )
