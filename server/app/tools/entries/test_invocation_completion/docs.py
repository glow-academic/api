"""Test invocation completion entry documentation."""

import asyncpg  # type: ignore

from app.infra.docs.get_mv_info import get_mv_info
from app.infra.docs.get_operation_info import get_operation_info
from app.infra.docs.get_table_info import get_table_info
from app.infra.docs.types import DocsResponse
from app.tools.entries.test_invocation_completion.create import (
    create_test_invocation_completion,
)
from app.tools.entries.test_invocation_completion.get import (
    get_test_invocation_completions,
)
from app.tools.entries.test_invocation_completion.refresh import (
    refresh_test_invocation_completion,
)
from app.tools.entries.test_invocation_completion.search import (
    search_test_invocation_completions,
)


async def get_test_invocation_completion_docs(conn: asyncpg.Connection) -> DocsResponse:
    """Get full documentation for the test_invocation_completion entry."""
    mv_info = await get_mv_info(conn, "test_invocation_completion_mv")
    entry_table = await get_table_info(conn, "test_invocation_completion_entry")

    tables = [t for t in [entry_table] if t is not None]

    return DocsResponse(
        name="test_invocation_completion",
        type="entry",
        description=(
            "Test invocation completion tracking. Records when an invocation completes "
            "within a test, including stop/error status and message. "
            "Links to test_invocation entries. "
            "Reads are served from the test_invocation_completion_mv materialized view."
        ),
        materialized_view=mv_info,
        tables=tables,
        operations=[
            get_operation_info(
                create_test_invocation_completion,
                description=(
                    "Creates a test_invocation_completion entry with invocation_id, "
                    "call_id, stop, error, and message."
                ),
            ),
            get_operation_info(
                refresh_test_invocation_completion,
                description="Refreshes test_invocation_completion_mv concurrently to reflect latest writes.",
            ),
            get_operation_info(
                get_test_invocation_completions,
                description="Batch retrieves test_invocation_completion entries by IDs from test_invocation_completion_mv.",
            ),
            get_operation_info(
                search_test_invocation_completions,
                description="Filtered paginated search against test_invocation_completion_mv.",
            ),
        ],
    )
