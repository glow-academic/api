"""Test invocation bridge entry documentation."""

import asyncpg  # type: ignore

from app.infra.docs.get_mv_info import get_mv_info
from app.infra.docs.get_operation_info import get_operation_info
from app.infra.docs.get_table_info import get_table_info
from app.infra.docs.types import DocsResponse
from app.tools.entries.test_invocation_bridge.create import (
    create_test_invocation_bridge,
)
from app.tools.entries.test_invocation_bridge.get import (
    get_test_invocation_bridge,
)
from app.tools.entries.test_invocation_bridge.refresh import (
    refresh_test_invocation_bridge,
)
from app.tools.entries.test_invocation_bridge.search import (
    search_test_invocation_bridge,
)


async def get_test_invocation_bridge_docs(conn: asyncpg.Connection) -> DocsResponse:
    """Get full documentation for the test_invocation_bridge entry."""
    mv_info = await get_mv_info(conn, "test_invocation_bridge_mv")
    entry_table = await get_table_info(conn, "test_invocation_bridge_entry")

    tables = [t for t in [entry_table] if t is not None]

    return DocsResponse(
        name="test_invocation_bridge",
        type="entry",
        description=(
            "Test invocation bridge entries link tests to invocations via a session. "
            "This bridge table connects the test and invocation domains. "
            "Reads are served from the test_invocation_bridge_mv materialized view."
        ),
        materialized_view=mv_info,
        tables=tables,
        operations=[
            get_operation_info(
                create_test_invocation_bridge,
                description=(
                    "Creates a new test_invocation_bridge entry linking a test "
                    "to an invocation within a session."
                ),
            ),
            get_operation_info(
                get_test_invocation_bridge,
                description="Retrieves test_invocation_bridge entries by test_invocation IDs from MV.",
            ),
            get_operation_info(
                refresh_test_invocation_bridge,
                description="Refreshes test_invocation_bridge_mv concurrently to reflect latest writes.",
            ),
            get_operation_info(
                search_test_invocation_bridge,
                description="Filtered paginated search against test_invocation_bridge_mv.",
            ),
        ],
    )
