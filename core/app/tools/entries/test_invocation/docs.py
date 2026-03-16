"""Test invocation entry documentation."""

import asyncpg  # type: ignore

from app.infra.docs.get_mv_info import get_mv_info
from app.infra.docs.get_operation_info import get_operation_info
from app.infra.docs.get_table_info import get_table_info
from app.infra.docs.types import DocsResponse
from app.tools.entries.test_invocation.create import create_test_invocation
from app.tools.entries.test_invocation.get import get_test_invocations
from app.tools.entries.test_invocation.refresh import refresh_test_invocation
from app.tools.entries.test_invocation.search import (
    search_test_invocation_entries_internal,
)


async def get_test_invocation_docs(conn: asyncpg.Connection) -> DocsResponse:
    """Get full documentation for the test_invocation entry."""
    mv_info = await get_mv_info(conn, "test_invocation_mv")
    entry_table = await get_table_info(conn, "test_invocation_entry")

    tables = [t for t in [entry_table] if t is not None]

    return DocsResponse(
        name="test_invocation",
        type="entry",
        description=(
            "Test invocation configurations within a test. Each invocation defines a specific "
            "agent execution scenario with title, position, group/run assignments, and optional "
            "custom configuration. Links to test, agent groups, and test runs. "
            "Reads are served from the test_invocation_mv materialized view."
        ),
        materialized_view=mv_info,
        tables=tables,
        operations=[
            get_operation_info(
                create_test_invocation,
                description=(
                    "Creates a test_invocation entry with test_id, title, position, "
                    "group_id, use_custom flag, and optional config_signature."
                ),
            ),
            get_operation_info(
                refresh_test_invocation,
                description="Refreshes test_invocation_mv concurrently to reflect latest writes.",
            ),
            get_operation_info(
                get_test_invocations,
                description=(
                    "Batch retrieves test_invocation entries by IDs from test_invocation_mv, "
                    "including related grade, run, group, and model/voice/temperature data."
                ),
            ),
            get_operation_info(
                search_test_invocation_entries_internal,
                description=(
                    "Filtered paginated search against test_invocation_mv with declarative filters."
                ),
            ),
        ],
    )
