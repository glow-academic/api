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
    agents_connection = await get_table_info(
        conn, "test_invocation_runs_agents_connection"
    )

    tables = [t for t in [entry_table, agents_connection] if t is not None]

    return DocsResponse(
        name="test_invocation_runs",
        type="entry",
        description=(
            "Test invocation run assignments. Maps test invocations to agents and execution config. "
            "Reads are served from the test_invocation_runs_mv materialized view."
        ),
        materialized_view=mv_info,
        tables=tables,
        operations=[
            get_operation_info(
                create_test_invocation_runs,
                description=(
                    "Creates a test_invocation_runs entry with optional agent_ids "
                    "and execution-config connections."
                ),
            ),
            get_operation_info(
                refresh_test_invocation_runs,
                description="Refreshes test_invocation_runs_mv concurrently to reflect latest writes.",
            ),
            get_operation_info(
                get_test_invocation_runs,
                description="Batch retrieves test_invocation_runs entries by IDs from test_invocation_runs_mv.",
            ),
            get_operation_info(
                search_test_invocation_runs,
                description="Filtered paginated search against test_invocation_runs_mv.",
            ),
        ],
    )
