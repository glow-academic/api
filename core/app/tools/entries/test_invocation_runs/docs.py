"""Test invocation runs entry documentation."""

import asyncpg  # type: ignore

from app.infra.docs.get_mv_info import get_mv_info
from app.infra.docs.get_operation_info import get_operation_info
from app.infra.docs.get_table_info import get_table_info
from app.infra.docs.types import DocsResponse
from app.tools.entries.test_invocation_runs.create import (
    create_test_invocation_runs,
)
from app.tools.entries.test_invocation_runs.get import (
    get_test_invocation_runs,
)
from app.tools.entries.test_invocation_runs.refresh import (
    refresh_test_invocation_runs,
)
from app.tools.entries.test_invocation_runs.search import (
    search_test_invocation_runs,
)


async def get_test_invocation_runs_docs(
    conn: asyncpg.Connection,
) -> DocsResponse:
    """Get full documentation for the test_invocation_runs entry."""
    mv_info = await get_mv_info(conn, "test_invocation_runs_mv")
    entry_table = await get_table_info(conn, "test_invocation_runs_entry")

    tables = [t for t in [entry_table] if t is not None]

    return DocsResponse(
        name="test_invocation_runs",
        type="entry",
        description=(
            "Test invocation run binding row — links a test invocation to "
            "(a) the underlying runs_entry holding the model output, and "
            "(b) the parent test_invocation_traces_entry that carries the "
            "bundle config. Pure binding row; bundle config lives on the trace."
        ),
        materialized_view=mv_info,
        tables=tables,
        operations=[
            get_operation_info(
                create_test_invocation_runs,
                description=(
                    "Creates a test_invocation_runs binding row with optional "
                    "run_id (the runs_entry produced by /test/generate) and "
                    "test_invocation_traces_id (the parent trace)."
                ),
            ),
            get_operation_info(
                refresh_test_invocation_runs,
                description="Refreshes test_invocation_runs_mv concurrently.",
            ),
            get_operation_info(
                get_test_invocation_runs,
                description="Batch retrieves test_invocation_runs entries by IDs.",
            ),
            get_operation_info(
                search_test_invocation_runs,
                description="Filtered paginated search against test_invocation_runs_mv.",
            ),
        ],
    )
