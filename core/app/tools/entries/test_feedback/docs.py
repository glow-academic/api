"""Test feedback entry documentation."""

import asyncpg  # type: ignore

from app.infra.docs.get_mv_info import get_mv_info
from app.infra.docs.get_operation_info import get_operation_info
from app.infra.docs.get_table_info import get_table_info
from app.infra.docs.types import DocsResponse
from app.tools.entries.test_feedback.create import create_test_feedback
from app.tools.entries.test_feedback.get import get_test_feedbacks
from app.tools.entries.test_feedback.refresh import refresh_test_feedback
from app.tools.entries.test_feedback.search import (
    search_test_feedback_entries,
)


async def get_test_feedback_docs(conn: asyncpg.Connection) -> DocsResponse:
    """Get full documentation for the test_feedback entry."""
    mv_info = await get_mv_info(conn, "test_feedback_mv")
    entry_table = await get_table_info(conn, "test_feedback_entry")

    tables = [t for t in [entry_table] if t is not None]

    return DocsResponse(
        name="test_feedback",
        type="entry",
        description=(
            "Test grade feedback and scoring. Records feedback text and point metrics "
            "(total, total_points, pass_points) for grade assessments. "
            "Links to test_grade entries. "
            "Reads are served from the test_feedback_mv materialized view."
        ),
        materialized_view=mv_info,
        tables=tables,
        operations=[
            get_operation_info(
                create_test_feedback,
                description=(
                    "Creates a test_feedback entry with grade_id, total, feedback text, "
                    "total_points, and pass_points."
                ),
            ),
            get_operation_info(
                refresh_test_feedback,
                description="Refreshes test_feedback_mv concurrently to reflect latest writes.",
            ),
            get_operation_info(
                get_test_feedbacks,
                description="Batch retrieves test_feedback entries by IDs from test_feedback_mv.",
            ),
            get_operation_info(
                search_test_feedback_entries,
                description=(
                    "Filtered paginated search against test_feedback entries "
                    "from test_feedback_mv with declarative filters."
                ),
            ),
        ],
    )
