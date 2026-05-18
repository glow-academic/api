"""Test grade entry documentation."""

import asyncpg  # type: ignore

from app.infra.docs.get_mv_info import get_mv_info
from app.infra.docs.get_operation_info import get_operation_info
from app.infra.docs.get_table_info import get_table_info
from app.infra.docs.types import DocsResponse
from app.tools.entries.test_grade.create import create_test_grade
from app.tools.entries.test_grade.get import get_test_grades
from app.tools.entries.test_grade.refresh import refresh_test_grade
from app.tools.entries.test_grade.search import search_test_grades


async def get_test_grade_docs(conn: asyncpg.Connection) -> DocsResponse:
    """Get full documentation for the test_grade entry."""
    mv_info = await get_mv_info(conn, "test_grade_mv")
    entry_table = await get_table_info(conn, "test_grade_entry")

    tables = [t for t in [entry_table] if t is not None]

    return DocsResponse(
        name="test_grade",
        type="entry",
        description=(
            "Test invocation grading results. Records scoring metrics for each test invocation: "
            "passed/failed status, score, time taken, and reference to the run (agent execution). "
            "Links to test_invocation entries. "
            "Reads are served from the test_grade_mv materialized view."
        ),
        materialized_view=mv_info,
        tables=tables,
        operations=[
            get_operation_info(
                create_test_grade,
                description=(
                    "Creates a test_grade entry with invocation_id, run_id, "
                    "time_taken, passed status, and score."
                ),
            ),
            get_operation_info(
                refresh_test_grade,
                description="Refreshes test_grade_mv concurrently to reflect latest writes.",
            ),
            get_operation_info(
                get_test_grades,
                description="Batch retrieves test_grade entries by IDs from test_grade_mv.",
            ),
            get_operation_info(
                search_test_grades,
                description=(
                    "Filtered paginated search against test_grade entries "
                    "by invocation_id and run_id from test_grade_mv."
                ),
            ),
        ],
    )
