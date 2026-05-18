"""Attempt feedback entry documentation."""

import asyncpg  # type: ignore

from app.infra.docs.get_mv_info import get_mv_info
from app.infra.docs.get_operation_info import get_operation_info
from app.infra.docs.get_table_info import get_table_info
from app.infra.docs.types import DocsResponse
from app.tools.entries.attempt_feedback.create import create_attempt_feedback
from app.tools.entries.attempt_feedback.get import get_attempt_feedbacks
from app.tools.entries.attempt_feedback.refresh import (
    refresh_attempt_feedback,
)
from app.tools.entries.attempt_feedback.search import (
    search_attempt_feedback_entries,
)


async def get_attempt_feedback_docs(conn: asyncpg.Connection) -> DocsResponse:
    """Get full documentation for the attempt_feedback entry."""
    mv_info = await get_mv_info(conn, "attempt_feedback_mv")
    entry_table = await get_table_info(conn, "attempt_feedback_entry")
    conn_table = await get_table_info(conn, "feedbacks_standards_connection")

    tables = [t for t in [entry_table, conn_table] if t is not None]

    return DocsResponse(
        name="attempt_feedback",
        type="entry",
        description=(
            "Feedback records attached to grades, containing feedback text and a total score. "
            "Each feedback entry links to a grade and may connect to multiple standards. "
            "Reads are served from the attempt_feedback_mv materialized view."
        ),
        materialized_view=mv_info,
        tables=tables,
        operations=[
            get_operation_info(
                create_attempt_feedback,
                description=(
                    "Creates a new attempt_feedback entry linked to a grade "
                    "and optionally populates feedbacks_standards_connection."
                ),
            ),
            get_operation_info(
                refresh_attempt_feedback,
                description="Refreshes attempt_feedback_mv concurrently.",
            ),
            get_operation_info(
                get_attempt_feedbacks,
                description="Batch retrieves feedbacks by IDs from attempt_feedback_mv.",
            ),
            get_operation_info(
                search_attempt_feedback_entries,
                description="Filtered paginated search against attempt_feedback_mv.",
            ),
        ],
    )
