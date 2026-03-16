"""Attempt grade entry documentation."""

import asyncpg  # type: ignore

from app.infra.docs.get_mv_info import get_mv_info
from app.infra.docs.get_operation_info import get_operation_info
from app.infra.docs.get_table_info import get_table_info
from app.infra.docs.types import DocsResponse
from app.tools.entries.attempt_grade.create import create_attempt_grade
from app.tools.entries.attempt_grade.get import get_attempt_grades
from app.tools.entries.attempt_grade.refresh import refresh_attempt_grade
from app.tools.entries.attempt_grade.search import search_attempt_grades


async def get_attempt_grade_docs(conn: asyncpg.Connection) -> DocsResponse:
    """Get full documentation for the attempt_grade entry."""
    mv_info = await get_mv_info(conn, "attempt_grade_mv")
    entry_table = await get_table_info(conn, "attempt_grade_entry")

    tables = [t for t in [entry_table] if t is not None]

    return DocsResponse(
        name="attempt_grade",
        type="entry",
        description=(
            "Grade records containing score, pass status, and time taken metrics. "
            "Each grade references a chat and run, and optionally links to rubrics "
            "via attempt_chat_rubrics_connection. "
            "Reads are served from the attempt_grade_mv materialized view."
        ),
        materialized_view=mv_info,
        tables=tables,
        operations=[
            get_operation_info(
                create_attempt_grade,
                description=(
                    "Creates a new attempt_grade entry with metrics and "
                    "optionally populates attempt_chat_rubrics_connection."
                ),
            ),
            get_operation_info(
                refresh_attempt_grade,
                description="Refreshes attempt_grade_mv concurrently.",
            ),
            get_operation_info(
                get_attempt_grades,
                description="Batch retrieves grades by IDs from attempt_grade_mv.",
            ),
            get_operation_info(
                search_attempt_grades,
                description="Filtered paginated search against attempt_grade_mv.",
            ),
        ],
    )
