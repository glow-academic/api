"""Test entry documentation."""

import asyncpg  # type: ignore

from app.infra.docs.get_mv_info import get_mv_info
from app.infra.docs.get_operation_info import get_operation_info
from app.infra.docs.get_table_info import get_table_info
from app.infra.docs.types import DocsResponse
from app.tools.entries.test.create import create_test
from app.tools.entries.test.get import get_tests
from app.tools.entries.test.refresh import refresh_test
from app.tools.entries.test.search import search_tests


async def get_test_docs(conn: asyncpg.Connection) -> DocsResponse:
    """Get full documentation for the test entry."""
    mv_info = await get_mv_info(conn, "test_mv")
    entry_table = await get_table_info(conn, "test_entry")
    connection_table = await get_table_info(conn, "test_profiles_connection")

    tables = [t for t in [entry_table, connection_table] if t is not None]

    return DocsResponse(
        name="test",
        type="entry",
        description=(
            "Test configuration and metadata tracking. "
            "Each test defines evaluation parameters (name, description, invocation count, modes). "
            "Optional connection to profiles via test_profiles_connection. "
            "Reads are served from the test_mv materialized view."
        ),
        materialized_view=mv_info,
        tables=tables,
        operations=[
            get_operation_info(
                create_test,
                description=(
                    "Creates a new test entry with configuration (name, description, "
                    "num_invocations, infinite_mode, mcp) and optional profiles connection."
                ),
            ),
            get_operation_info(
                refresh_test,
                description="Refreshes test_mv concurrently to reflect latest writes.",
            ),
            get_operation_info(
                get_tests,
                description="Batch retrieves test entries by IDs from test_mv.",
            ),
            get_operation_info(
                search_tests,
                description=(
                    "Filtered paginated search against test entries "
                    "by eval_id and profile_id from test_mv."
                ),
            ),
        ],
    )
